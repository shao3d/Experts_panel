#!/usr/bin/env python
"""Measure comparison-query formulations against the same Reddit channel.

Question under test (measured 2026-10-18): the `comparison_anchor_relevance`
channel sends ``f"{anchor_terms[0]} {anchor_terms[1]} benchmark"``. Anchor
terms come from a structural specificity heuristic, so real owner questions
produced "5.3 good benchmark", "deepseek intel benchmark" and "code benchmark"
— strings that name one compared product at best and an adjective at worst.

Phase 1 (always) sends several formulations through the SAME channel
(``_search_with_sort(query, sort="relevance", time="year", limit=18)``), so the
only variable is the query string, and scores each arm with judge-free metrics:

* ``both_entities`` — returned posts mentioning BOTH compared things
  (title+selftext alias match) plus a comparison marker. Hand-written reference
  aliases per question; objective and cheap.
* ``winners_found`` — posts the live pipeline actually selected for that
  question (from `data/reddit_search_telemetry.jsonl`) that this arm
  rediscovers. Biased in favour of the arm that ran live, so it is a
  *replacement* check, not a quality check.

Phase 2 (``--judge``) settles quality: it builds the control+entity union pool,
attributes each post to the arms that found it, runs the production judge and
confidence gate ONCE per question, and reports selection rates for
arm-exclusive posts — the only comparison the judge noise cannot fake, because
both arms are scored in the same call.

Usage (from backend/; local dev, owner-authorized live runs):
    REDDIT_PROXY_URL=http://localhost:3000 .venv/bin/python -u \
        scripts/reddit_comparison_entities_probe.py --questions 12 --judge
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src import config  # noqa: E402
from src.services.reddit_enhanced_service import (  # noqa: E402
    RedditEnhancedService,
    _extract_comparison_entities,
)

TELEMETRY_PATH = BACKEND / "data" / "reddit_search_telemetry.jsonl"
DEFAULT_OUT = BACKEND.parent / "output" / "ab_reddit" / "comparison_entities_report.json"

# Hand-written reference entities per question (substring key): each entry is
# one compared thing with its accepted aliases, all lowercase.
REFERENCES: List[Tuple[str, List[List[str]]]] = [
    ("Xiaomi MiMo V2.6 Pro vs GLM-5.3 Flash", [["mimo"], ["glm-5.3", "glm 5.3", "glm5.3"]]),
    (
        "GLM-5.3 Flash vs DeepSeek V4.1 Flash agentic research",
        [["glm-5.3", "glm 5.3", "glm5.3"], ["deepseek v4.1", "v4.1", "deepseek-v4.1"]],
    ),
    (
        "best value models GLM-5.3 Flash GPT-5.6 Sol DeepSeek V4.1",
        [["glm-5.3", "glm 5.3"], ["gpt-5.6", "gpt 5.6"]],
    ),
    (
        "best value LLM models GLM-5.3 Kimi K3 Qwen 3.8 Max",
        [["glm-5.3", "glm 5.3"], ["kimi k3", "kimi-k3", "k3"]],
    ),
    ("OpenAI GPT Image 2.5 Sunburst versus Flare Codex routing", [["sunburst"], ["flare"]]),
    (
        "Which image generation model does the built-in Codex app image_gen",
        [["gpt image 2"], ["gpt image 1.5", "gpt image 1"]],
    ),
    (
        "DeepSeek Harness dsh CLI desktop app experience",
        [["deepseek harness", "dsh"], ["claude code", "claude"]],
    ),
    (
        "What do developers on Reddit say about DeepSeek Harness (dsh)",
        [["deepseek harness", "dsh"], ["claude code", "claude"]],
    ),
    ("Is Thinking Machines' Inkling model as good as GLM 5.3", [["inkling"], ["glm 5.3", "glm-5.3"]]),
    (
        "What do Reddit users report about GLM-5.3 Flash latency versus DeepSeek V4.1",
        [["glm-5.3", "glm 5.3"], ["deepseek v4.1", "v4.1"]],
    ),
    ("Xiaomi MiMo V2.6 Pro: how smart is it vs GLM-5.3 Flash", [["mimo"], ["glm-5.3", "glm 5.3"]]),
    ("Current Reddit reports: OpenAI GPT Image 2.5 Sunburst versus Flare", [["sunburst"], ["flare"]]),
    (
        "Command Code GOAT plan: which models do practitioners say give the best value",
        [["glm-5.3", "glm 5.3"], ["kimi k3", "kimi-k3"]],
    ),
    ("r/CommandCode subreddit GOAT", [["glm-5.3", "glm 5.3"], ["kimi k3", "kimi-k3"]]),
]

COMPARISON_MARKERS = (
    " vs ", " vs.", "versus", "compared to", "compared with", "compare to",
    "better than", "worse than", "difference between", "which is better",
)


def _reference_for(query: str) -> Optional[List[List[str]]]:
    for key, reference in REFERENCES:
        if key.lower() in query.lower():
            return reference
    return None


def _load_questions(limit: int) -> List[Dict[str, Any]]:
    """Most recent live comparison search per question text, winners included."""
    if not TELEMETRY_PATH.exists():
        raise SystemExit(f"telemetry log not found: {TELEMETRY_PATH}")

    latest: Dict[str, Dict[str, Any]] = {}
    with TELEMETRY_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("intent") != "comparison":
                continue
            query = (record.get("query") or "").strip()
            if query:
                latest[query] = record

    selected: List[Dict[str, Any]] = []
    for query, record in sorted(
        latest.items(), key=lambda item: item[1].get("ts", ""), reverse=True
    ):
        reference = _reference_for(query)
        if not reference:
            continue
        selected.append(
            {
                "query": query,
                "plan_query": (record.get("plan_query") or query).strip(),
                "reference": reference,
                "winner_ids": [
                    w.get("id") for w in (record.get("winners") or []) if w.get("id")
                ],
                "ts": record.get("ts"),
            }
        )
        if len(selected) >= limit:
            break
    return selected


def _mentions(text: str, reference: List[List[str]]) -> int:
    low = (text or "").lower()
    return sum(1 for group in reference if any(alias in low for alias in group))


def _has_marker(text: str) -> bool:
    low = f" {(text or '').lower()} "
    return any(marker in low for marker in COMPARISON_MARKERS)


def _arm_queries(question: Dict[str, Any], service: RedditEnhancedService) -> Dict[str, str]:
    query = question["query"]
    anchors = service._extract_anchor_terms(query)
    entities = _extract_comparison_entities(query)
    arms = {
        # Exactly what comparison_anchor_relevance sends today.
        "control": (" ".join(anchors[:2]) + " benchmark").strip(),
        # Exactly what literal_global_relevance / serp_google_discovery send.
        "plan": question["plan_query"],
    }
    if len(entities) >= 2:
        arms["entity"] = " ".join(entities)
        arms["entity_vs"] = f"{entities[0]} vs {entities[1]}"
        # Does the control query's effect come from its suffix rather than from
        # its (broken) names? "names + benchmark" separates the two.
        arms["entity_benchmark"] = f"{' '.join(entities[:2])} benchmark"
    return arms


async def _fresh_search(proxy_url: str, query: str, limit: int):
    """One search on a private service: a transient error must not trip a
    shared circuit breaker and silently zero the remaining arms."""
    service = RedditEnhancedService(base_url=proxy_url)
    try:
        return await service._search_with_sort(
            query, sort="relevance", limit=limit, time="year"
        )
    finally:
        if service._client is not None and not service._client.is_closed:
            await service._client.aclose()


async def judge_union(
    service: RedditEnhancedService,
    question: Dict[str, Any],
    results: Dict[str, List[Any]],
    anchor_terms: List[str],
    *,
    cut: int = 0,
    enrich: bool = False,
) -> Dict[str, Any]:
    """Judge the control+entity union once; attribute the gate per arm.

    ``cut`` mirrors the production candidate cut (REDDIT_RERANK_CANDIDATES):
    with a cut the winner is the arm that occupies and survives the judged
    slots, exactly as production would experience it. ``enrich`` fetches
    /details for the judged set first, because the evidence gate needs quotable
    text and production always enriches before judging — without it an arm can
    lose on "snippet-only post", not on relevance.
    """
    pool: Dict[str, Any] = {}
    arms_by_id: Dict[str, List[str]] = {}
    for arm in ("control", "entity", "entity_benchmark"):
        for post in results.get(arm) or []:
            arms_by_id.setdefault(post.id, []).append(arm)
            pool.setdefault(post.id, post)
    posts = list(pool.values())
    if not posts:
        return {"pool": 0}

    # `search_enhanced` scores every unique candidate before the judge; the
    # anchor/comparison gates read those fields, so skipping this step would
    # reject the whole pool for the wrong reason (measured: 0 selected, tier
    # abstain, on a pool that contained the live winners).
    query_terms = service._tokenize_query_terms(question["query"])
    for post in posts:
        post.heuristic_score = service._score_post_v2(
            post,
            query_terms=query_terms,
            anchor_terms=anchor_terms,
            target_keywords=[],
            intent="comparison",
        )

    posts.sort(key=lambda p: p.heuristic_score, reverse=True)
    slots_by_arm: Dict[str, int] = {}
    if cut:
        posts = posts[:cut]
    for post in posts:
        for arm in arms_by_id.get(post.id, []):
            slots_by_arm[arm] = slots_by_arm.get(arm, 0) + 1

    if enrich:
        enriched = await asyncio.gather(
            *[service._enrich_post_content(post) for post in posts],
            return_exceptions=True,
        )
        posts = [
            item if not isinstance(item, Exception) else original
            for item, original in zip(enriched, posts)
        ]

    started = time.monotonic()
    ranked = await service._ai_rerank_posts(
        question["plan_query"],
        posts,
        intent="comparison",
        anchor_terms=anchor_terms,
        original_user_query=question["query"],
    )
    latency = time.monotonic() - started

    judge_unavailable = bool(ranked) and all(
        p.evidence_status == "unavailable" for p in ranked
    )
    tier: Dict[str, Any] = {}
    selected = service._apply_confidence_threshold(
        ranked,
        target_posts=25,
        require_anchor_match=bool(anchor_terms),
        intent="comparison",
        judge_unavailable=judge_unavailable,
        tier_out=tier,
    )
    selected_ids = {p.id for p in selected}

    per_arm: Dict[str, Dict[str, Any]] = {}
    for arm in ("control", "entity", "entity_benchmark"):
        exclusive = [pid for pid, arms in arms_by_id.items() if arms == [arm]]
        per_arm[arm] = {
            "pool": sum(1 for pid in arms_by_id if arm in arms_by_id[pid]),
            "exclusive": len(exclusive),
            "exclusive_selected": sum(1 for pid in exclusive if pid in selected_ids),
        }
    shared = [pid for pid, arms in arms_by_id.items() if len(arms) > 1]
    return {
        "pool": len(posts),
        "cut": cut,
        "enriched": bool(enrich),
        "slots_by_arm": slots_by_arm,
        "shared": len(shared),
        "shared_selected": sum(1 for pid in shared if pid in selected_ids),
        "judge_latency_s": round(latency, 1),
        "judge_unavailable": judge_unavailable,
        "decision_tier": tier.get("decision_tier"),
        "verified": sum(1 for p in ranked if p.evidence_status == "verified"),
        "selected": len(selected_ids),
        "per_arm": per_arm,
        "posts": [
            {
                "id": p.id,
                "arms": arms_by_id.get(p.id, []),
                "sub": p.subreddit,
                "title": (p.title or "")[:110],
                "both_entities": _mentions(f"{p.title} {p.selftext}", question["reference"]) >= 2,
                "ai": round(p.ai_score, 3),
                "final": round(p.final_score, 3),
                "evidence": p.evidence_status,
                "selected": p.id in selected_ids,
            }
            for p in ranked
        ],
    }


async def run(args: argparse.Namespace, out_path: Path) -> int:
    questions = _load_questions(args.questions)
    if not questions:
        raise SystemExit("no comparison questions with a reference mapping found")

    proxy_url = args.proxy or config.REDDIT_PROXY_URL
    # A union pool is ~2x the production candidate set; the production 90s
    # budget is for one shipped pool, not for a measurement.
    config.REDDIT_DSH_TIMEOUT_S = max(config.REDDIT_DSH_TIMEOUT_S, 240)

    print(f"proxy: {proxy_url} | questions: {len(questions)} | judge: {args.judge}")
    helper = RedditEnhancedService(base_url=proxy_url)
    report: Dict[str, Any] = {
        "proxy": proxy_url,
        "search_limit": args.search_limit,
        "sort": "relevance",
        "time": "year",
        "judged": bool(args.judge),
        "cut": args.cut,
        "enrich": bool(args.enrich),
        "questions": [],
    }
    totals: Dict[str, Dict[str, float]] = {}

    for index, question in enumerate(questions, start=1):
        arms = _arm_queries(question, helper)
        anchor_terms = helper._extract_anchor_terms(question["query"])
        print(f"\n[{index}/{len(questions)}] {question['query'][:88]}")
        print(f"    entities -> {_extract_comparison_entities(question['query'])}")

        results: Dict[str, List[Any]] = {}
        for arm, query in arms.items():
            print(f"    {arm:9s} q={query[:66]!r}")
            try:
                results[arm] = await _fresh_search(proxy_url, query, args.search_limit)
            except Exception as exc:  # noqa: BLE001 - probe must survive one bad arm
                print(f"      !! {arm} failed: {exc}")
                results[arm] = []
            await asyncio.sleep(args.pause)

        ids_by_arm = {arm: {p.id for p in posts} for arm, posts in results.items()}
        winner_ids: Set[str] = set(question["winner_ids"])
        entry: Dict[str, Any] = {
            "query": question["query"],
            "plan_query": question["plan_query"],
            "anchor_terms": anchor_terms,
            "reference": question["reference"],
            "winner_ids": sorted(winner_ids),
            "arms": {},
        }
        for arm, posts in results.items():
            both = [
                p
                for p in posts
                if _mentions(f"{p.title} {p.selftext}", question["reference"]) >= 2
            ]
            both_marked = [p for p in both if _has_marker(f"{p.title} {p.selftext}")]
            found_winners = sorted({p.id for p in posts} & winner_ids)
            novel = [
                p.id
                for p in posts
                if not any(p.id in ids_by_arm[other] for other in ids_by_arm if other != arm)
            ]
            entry["arms"][arm] = {
                "query": arms[arm],
                "returned": len(posts),
                "both_entities": len(both),
                "both_entities_marked": len(both_marked),
                "winners_found": found_winners,
                "novel": novel,
                "titles": [
                    {
                        "id": p.id,
                        "sub": p.subreddit,
                        "title": (p.title or "")[:110],
                        "both": _mentions(f"{p.title} {p.selftext}", question["reference"]) >= 2,
                        "winner": p.id in winner_ids,
                    }
                    for p in posts
                ],
            }
            agg = totals.setdefault(
                arm,
                {"returned": 0.0, "both": 0.0, "marked": 0.0, "winners": 0.0, "questions": 0.0},
            )
            agg["returned"] += len(posts)
            agg["both"] += len(both)
            agg["marked"] += len(both_marked)
            agg["winners"] += len(found_winners)
            agg["questions"] += 1
            print(
                f"      -> {len(posts):2d} posts | both-entity {len(both):2d} "
                f"(marked {len(both_marked):2d}) | winners {len(found_winners)}/{len(winner_ids)}"
            )

        if args.judge and results.get("control") and results.get("entity"):
            judged = await judge_union(
                helper,
                question,
                results,
                anchor_terms,
                cut=args.cut,
                enrich=args.enrich,
            )
            entry["judge"] = judged
            control_stats = judged.get("per_arm", {}).get("control", {})
            entity_stats = judged.get("per_arm", {}).get("entity", {})
            jt = totals.setdefault(
                "judge",
                {
                    "pool": 0.0, "selected": 0.0, "ctrl_excl": 0.0, "ctrl_excl_sel": 0.0,
                    "ent_excl": 0.0, "ent_excl_sel": 0.0, "questions": 0.0,
                },
            )
            jt["pool"] += judged.get("pool", 0)
            jt["selected"] += judged.get("selected", 0)
            jt["ctrl_excl"] += control_stats.get("exclusive", 0)
            jt["ctrl_excl_sel"] += control_stats.get("exclusive_selected", 0)
            jt["ent_excl"] += entity_stats.get("exclusive", 0)
            jt["ent_excl_sel"] += entity_stats.get("exclusive_selected", 0)
            jt["questions"] += 1
            print(
                f"    judge: pool {judged.get('pool')} (slots {judged.get('slots_by_arm')}) "
                f"selected {judged.get('selected')} "
                f"verified {judged.get('verified')} tier {judged.get('decision_tier')} "
                f"{judged.get('judge_latency_s')}s | exclusive ctrl "
                f"{control_stats.get('exclusive_selected')}/{control_stats.get('exclusive')} "
                f"ent {entity_stats.get('exclusive_selected')}/{entity_stats.get('exclusive')}"
            )

        report["questions"].append(entry)
        report["totals"] = totals
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if helper._client is not None and not helper._client.is_closed:
        await helper._client.aclose()

    print("\n=== totals (phase 1) ===")
    print(f"{'arm':12s} {'posts':>7s} {'both':>6s} {'marked':>7s} {'winners':>8s}")
    for arm, agg in sorted(totals.items()):
        if arm == "judge":
            continue
        print(
            f"{arm:12s} {int(agg['returned']):7d} {int(agg['both']):6d} "
            f"{int(agg['marked']):7d} {int(agg['winners']):8d}"
        )
    if "judge" in totals:
        jt = totals["judge"]
        print("\n=== judge (control+entity union, one call per question) ===")
        print(
            f"pool {int(jt['pool'])} posts | selected {int(jt['selected'])} total\n"
            f"control-exclusive selected {int(jt['ctrl_excl_sel'])}/{int(jt['ctrl_excl'])}\n"
            f"entity-exclusive  selected {int(jt['ent_excl_sel'])}/{int(jt['ent_excl'])}"
        )
    print(f"\nreport: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=int, default=12, help="how many questions to probe")
    parser.add_argument(
        "--search-limit",
        type=int,
        default=18,
        help="posts per arm (channel parity: comparison_anchor_relevance uses 18)",
    )
    parser.add_argument("--pause", type=float, default=1.2, help="seconds between requests")
    parser.add_argument("--proxy", default=os.getenv("REDDIT_PROXY_URL", ""), help="reddit-proxy base URL")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report path")
    parser.add_argument("--judge", action="store_true", help="also judge the control+entity union")
    parser.add_argument(
        "--cut",
        type=int,
        default=0,
        help="mirror the production candidate cut (0 = judge the whole union)",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="fetch /details for the judged set first, as production does",
    )
    args = parser.parse_args()
    return asyncio.run(run(args, Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
