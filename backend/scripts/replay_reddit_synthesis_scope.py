#!/usr/bin/env python3
"""Replay Reddit synthesis on frozen shortlists to measure the coverage scope.

Phase B of the V2 fix plan changes which verdict the synthesizer may reach:

  B1  `insufficient` is reserved for the central request; an unsupported
      secondary constraint makes the answer partial instead of an abstain
  B2  a stray gap sentence no longer downgrades a sufficient answer
  B3  a partial answer carries up to five findings instead of three

That is a prompt/contract change, so it has to be measured on IDENTICAL
shortlists: a fresh retrieval would confound the prompt effect with retrieval
drift. This harness freezes the shortlist and swaps only the contract.

    --capture [N]    run the live V2 pipeline for the questions already used by
                     ab_reddit_dsh_vs_gemini.py and freeze the posts it selected
                     (slow: one full live search per question)
    --from-report    rebuild the same shortlists offline from that harness's
                     report + fixtures (fast, no retrieval)
    --replay --arm   run synthesis on those frozen shortlists with the current
                     contract (new), the pre-phase-B contract (old), or both

The old arm restores the previous prompt text, REDDIT_SYNTH_GAP_FORCES_PARTIAL
and REDDIT_SYNTH_PARTIAL_MAX_FINDINGS, so the two arms differ in nothing else.
Unlike replay_reddit_synthesis.py (the isolated Gemini-era A/B with a baseline
source file), this one drives the configured engine — today dsh — so it
measures the contract that actually ships.

Output: output/ab_reddit/shortlists*.jsonl and synth_<source>_<arm>.jsonl

Usage (local dev; the owner authorized live runs):
    REDDIT_PROXY_URL=http://localhost:3000 \
    DSH_PATCH_PATH=backend/deploy/dsh/reddit-llm.patch.yml \
      backend/.venv/bin/python backend/scripts/replay_reddit_synthesis_scope.py --capture 22
    backend/.venv/bin/python backend/scripts/replay_reddit_synthesis_scope.py --from-report
    DSH_PATCH_PATH=backend/deploy/dsh/reddit-llm.patch.yml \
      backend/.venv/bin/python backend/scripts/replay_reddit_synthesis_scope.py --replay --arm both
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src import config  # noqa: E402
from src.services.reddit_enhanced_service import (  # noqa: E402
    RedditPost,
    get_reddit_enhanced_service,
)
from src.services.reddit_synthesis_service import (  # noqa: E402
    RedditSynthesisService,
)

RESULTS_DIR = BACKEND.parent / "output" / "ab_reddit"
SHORTLIST_PATH = RESULTS_DIR / "shortlists.jsonl"
REPORT_SHORTLIST_PATH = RESULTS_DIR / "shortlists_from_report.jsonl"
PHASE_A_REPORT = RESULTS_DIR / "report.json"

# Exactly the clause B1 inserted into the synthesis prompt. The old arm removes
# it, which reproduces the pre-phase-B wording verbatim.
B1_CLAUSE = (
    "Reserve\n"
    "coverage=insufficient for the case where the sources do not establish the\n"
    "question's CENTRAL request (the comparison, decision or fix the user actually\n"
    "asked for): an unsupported secondary constraint (a version, region, price\n"
    "point, extra example or an additional named tool) makes the answer partial,\n"
    "not insufficient. "
)
PARTIAL_BANNERS = (
    "**The evidence supports only a partial answer.**",
    "**Данных достаточно только для частичного ответа.**",
)
POST_FIELDS = {
    "id",
    "title",
    "url",
    "permalink",
    "score",
    "num_comments",
    "subreddit",
    "author",
    "created_utc",
    "selftext",
    "is_self",
    "is_technical_guide",
    "heuristic_score",
    "anchor_matches",
    "title_anchor_matches",
    "body_anchor_matches",
    "comment_anchor_matches",
    "title_body_anchor_matches",
    "direct_comparison_hits",
    "ai_score",
    "final_score",
    "ranking_reason",
    "evidence_span",
    "evidence_status",
    "evidence_source",
    "evidence_context",
    "top_comments",
}


# --- phase 1: freeze real shortlists -----------------------------------------


def reference_queries() -> List[str]:
    """The same questions the judge A/B used, in the same order."""
    if PHASE_A_REPORT.exists():
        report = json.loads(PHASE_A_REPORT.read_text(encoding="utf-8"))
        queries = [
            row["query"] for row in report.get("per_question", []) if row.get("query")
        ]
        if queries:
            return queries
    queries = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        if path.name.startswith(("report", "synth")):
            continue
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if fixture.get("query"):
            queries.append(fixture["query"])
    return queries


def shortened_query(query: str, limit: int = 64) -> str:
    query = " ".join(query.split())
    return query if len(query) <= limit else query[: limit - 1] + "…"


def load_shortlists(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = path or SHORTLIST_PATH
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_shortlists_from_report() -> List[Dict[str, Any]]:
    """Reconstruct the phase A shortlists offline from the judge A/B report.

    The report holds, per question, the judge's verdict for every candidate
    (`judged[]`) and which of them passed the gate (`selected`), while the
    fixtures hold the full post bodies and comment trees. Joining the two
    reproduces exactly what synthesis receives, without another live retrieval —
    and, because both arms see the same shortlist, retrieval drift cannot be
    mistaken for an effect of the contract.
    """
    from src.services.reddit_evidence import select_evidence_passages

    if not PHASE_A_REPORT.exists():
        return []
    report = json.loads(PHASE_A_REPORT.read_text(encoding="utf-8"))
    fixtures = {}
    for path in sorted(RESULTS_DIR.glob("*.json")):
        if path.name.startswith(("report", "synth")):
            continue
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if fixture.get("query"):
            fixtures[fixture["query"]] = fixture

    rebuilt: List[Dict[str, Any]] = []
    for row in report.get("per_question", []):
        fixture = fixtures.get(row["query"])
        if fixture is None or not row.get("selected"):
            continue
        judged = {entry["id"]: entry for entry in row.get("judged", [])}
        passages_query = " ".join(
            filter(
                None,
                [
                    fixture.get("plan_query") or fixture["query"],
                    fixture["query"],
                    *(fixture.get("anchor_terms") or []),
                ],
            )
        )
        posts = []
        for payload in fixture.get("candidates", []):
            entry = judged.get(payload.get("id"))
            if entry is None or payload["id"] not in row["selected"]:
                continue
            post = {key: value for key, value in payload.items() if key in POST_FIELDS}
            post["ai_score"] = entry["ai"]
            post["final_score"] = entry["final"]
            post["evidence_status"] = entry["evidence"]
            post["evidence_span"] = entry.get("span") or ""
            post["ranking_reason"] = entry.get("reason") or ""
            if entry["evidence"] in {"verified", "verified_normalized"}:
                post["evidence_context"] = "\n".join(
                    passage.render()
                    for passage in select_evidence_passages(
                        RedditPost(**post), passages_query
                    )
                )
            posts.append(post)
        if not posts:
            continue
        rebuilt.append(
            {
                "query": row["query"],
                "source": "report",
                "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "unique_posts": row.get("candidates") or len(fixture.get("candidates", [])),
                "decision_tier": row.get("decision_tier"),
                "judge_unavailable": bool(row.get("judge_unavailable")),
                "reflection_retry_used": False,
                "reflection_retry_trigger": None,
                "posts": posts,
            }
        )
    return rebuilt


async def capture_one(service: Any, query: str) -> Dict[str, Any]:
    started = time.monotonic()
    result = await service.search_enhanced(
        query=query,
        target_posts=25,
        include_comments=True,
        original_user_query=query,
    )
    elapsed = time.monotonic() - started
    trace = getattr(result, "debug_trace", {}) or {}
    return {
        "query": query,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "live_latency_s": round(elapsed, 1),
        "unique_posts": result.total_found,
        "decision_tier": trace.get("decision_tier"),
        "judge_unavailable": bool(trace.get("judge_unavailable")),
        "reflection_retry_used": bool(trace.get("reflection_retry_used")),
        "reflection_retry_trigger": trace.get("reflection_retry_trigger"),
        "posts": [
            {
                key: value
                for key, value in dataclasses.asdict(post).items()
                if key in POST_FIELDS
            }
            for post in result.posts
        ],
    }


async def run_capture(limit: int, pause_s: float) -> int:
    queries = reference_queries()
    if not queries:
        print("no reference questions found; run the judge A/B capture first")
        return 1
    if limit:
        queries = queries[:limit]
    done = {row["query"] for row in load_shortlists()}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    service = get_reddit_enhanced_service()
    try:
        with SHORTLIST_PATH.open("a", encoding="utf-8") as handle:
            for index, query in enumerate(queries, 1):
                if query in done:
                    print(f"[{index}/{len(queries)}] cached: {query[:56]}")
                    continue
                label = query[:56]
                try:
                    row = await capture_one(service, query)
                except Exception as exc:
                    print(f"[{index}/{len(queries)}] FAILED {label}: {exc}")
                    continue
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                print(
                    f"[{index}/{len(queries)}] {label} | kept={len(row['posts'])} "
                    f"of {row['unique_posts']} | tier={row['decision_tier']} "
                    f"retry={row['reflection_retry_trigger']} | {row['live_latency_s']}s"
                )
                if pause_s:
                    await asyncio.sleep(pause_s)
    finally:
        await service.close()
    return 0


# --- phase 2: offline synthesis replay ---------------------------------------


def classify(text: str, post_count: int = 1) -> str:
    """Coarse verdict from the rendered answer, not from the model's JSON.

    An empty shortlist never reaches coverage assessment: synthesize() returns
    the "no community discussions" line and the API reports an abstain caused
    by retrieval, not a coverage verdict. Counting that as `sufficient` would
    flatter the contract.
    """
    if post_count == 0:
        return "no_sources"
    if RedditSynthesisService.is_explicit_abstention(text):
        return "insufficient"
    if any(banner in text for banner in PARTIAL_BANNERS):
        return "partial"
    return "sufficient"


def apply_arm(arm: str) -> None:
    """Point the service at the contract under test. Defaults are the new one."""
    if arm == "new":
        return
    original = RedditSynthesisService._create_synthesis_prompt

    def old_prompt(self, query, context, query_language="English"):
        messages = original(self, query, context, query_language)
        patched = []
        replaced = False
        for message in messages:
            content = message.get("content") or ""
            if B1_CLAUSE in content:
                content = content.replace(B1_CLAUSE, "")
                replaced = True
            patched.append({**message, "content": content})
        # Only the system prompt carries the clause; the check is that the
        # reversion really happened, not that every message contained it.
        assert replaced, "phase B clause not found in the prompt"
        return patched

    RedditSynthesisService._create_synthesis_prompt = old_prompt
    config.REDDIT_SYNTH_GAP_FORCES_PARTIAL = True
    config.REDDIT_SYNTH_PARTIAL_MAX_FINDINGS = 3


class ReplayResult:
    """Minimal EnhancedSearchResult stand-in for the frozen shortlist."""

    def __init__(self, posts: List[RedditPost], total_found: int, query: str) -> None:
        self.posts = posts
        self.total_found = total_found
        self.query = query
        self.strategies_used: List[str] = []
        self.processing_time_ms = 0
        self.debug_trace: Dict[str, Any] = {}


async def synthesize_row(
    row: Dict[str, Any], service: RedditSynthesisService, semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    posts = [RedditPost(**payload) for payload in row["posts"]]
    result = ReplayResult(posts, row.get("unique_posts") or len(posts), row["query"])
    async with semaphore:
        started = time.monotonic()
        try:
            text = await service.synthesize(row["query"], result)
            error = None
        except Exception as exc:  # a contract error is a result, not a crash
            text, error = "", f"{type(exc).__name__}: {exc}"
        elapsed = time.monotonic() - started
    verdict = "error" if error else classify(text, len(posts))
    return {
        "query": row["query"],
        "shortlist": len(posts),
        "verdict": verdict,
        "error": error,
        "latency_s": round(elapsed, 1),
        "findings": text.count("- **"),
        "chars": len(text),
        "gap_rendered": "Not established by the sources:" in text,
        "answer": text,
    }


async def run_replay(
    arm: str, limit: int, concurrency: int, shortlists: Optional[str] = None
) -> int:
    rows = load_shortlists(SHORTLIST_PATH if not shortlists else Path(shortlists))
    if not rows:
        print(f"no shortlists in {SHORTLIST_PATH}; run --capture first")
        return 1
    if limit:
        rows = rows[:limit]
    apply_arm(arm)
    service = RedditSynthesisService()
    semaphore = asyncio.Semaphore(concurrency)
    started = time.monotonic()
    results = await asyncio.gather(
        *[synthesize_row(row, service, semaphore) for row in rows]
    )
    stem = Path(shortlists).stem if shortlists else "shortlists"
    target = RESULTS_DIR / f"synth_{stem}_{arm}.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    verdicts = [row["verdict"] for row in results]
    latencies = [row["latency_s"] for row in results]
    print(f"\n--- synthesis replay ({arm}) ---")
    print(f"questions: {len(results)} | wall clock: {time.monotonic() - started:.0f}s")
    for verdict in ("sufficient", "partial", "insufficient", "error"):
        count = verdicts.count(verdict)
        print(f"{verdict:<13} {count:>3}  {count / len(results):.1%}")
    if latencies:
        p90_index = max(0, min(len(latencies) - 1, int(len(latencies) * 0.9)))
        print(
            f"latency: median {statistics.median(latencies):.1f}s "
            f"p90 {sorted(latencies)[p90_index]:.1f}s"
        )
    thin = [row for row in results if row["shortlist"] < 2]
    if thin:
        print("thin shortlist: " + ", ".join(row["verdict"] for row in thin))
    print(f"written: {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=int, nargs="?", const=0, metavar="N")
    parser.add_argument("--from-report", action="store_true")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--arm", choices=["new", "old", "both"], default="both")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--concurrency", type=int, default=int(config.REDDIT_DSH_CONCURRENCY)
    )
    parser.add_argument("--pause", type=float, default=3.0)
    parser.add_argument(
        "--shortlists",
        help="JSONL of frozen shortlists (default: the live capture file)",
    )
    args = parser.parse_args()

    if args.from_report:
        rows = build_shortlists_from_report()
        if not rows:
            print("report/fixtures missing; run the judge A/B first")
            return 1
        target = Path(args.shortlists) if args.shortlists else REPORT_SHORTLIST_PATH
        with target.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"rebuilt {len(rows)} shortlists from the phase A report -> {target}")
        for row in rows:
            print(
                f"  kept={len(row['posts'])} of {row['unique_posts']} "
                f"| tier={row['decision_tier']} | {shortened_query(row['query'], 52)}"
            )
        return 0
    if args.capture is not None:
        return asyncio.run(run_capture(args.capture, args.pause))
    if args.replay:
        arms = ["new", "old"] if args.arm == "both" else [args.arm]
        for arm in arms:
            code = asyncio.run(
                run_replay(arm, args.limit, max(1, args.concurrency), args.shortlists)
            )
            if code:
                return code
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
