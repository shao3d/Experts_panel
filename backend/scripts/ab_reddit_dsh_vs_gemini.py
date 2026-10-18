#!/usr/bin/env python3
"""A/B: the dsh judge against the recorded Gemini decisions.

Why this shape: the production telemetry stores Gemini's *decisions* (winning
post IDs, scores, evidence status, reject reasons) but neither the candidate
texts nor its answer. So the comparison is decision-level, in two phases:

    --capture   run live V2 retrieval for the owner's own questions, dumping
                the exact judge candidates (full body + comment tree) to
                fixtures before any scoring happens
    --replay    run the judge offline on those frozen fixtures and compare the
                selected posts with the telemetry reference

Frozen fixtures make every later prompt/effort experiment comparable: only the
judge changes between runs, the candidate pool does not.

Metrics per question:
  available   - recorded Gemini winners that are still present in today's pool
                (retrieval drift is measured, not hidden)
  agreement   - of those available posts, the share the dsh judge also selects
  verified    - share of judged posts with a verbatim quote
  unrated     - posts the judge returned no usable rating for

Usage (local dev; the owner authorized live runs):
    REDDIT_PROXY_URL=http://localhost:3000 \
    DSH_PATCH_PATH=backend/deploy/dsh/reddit-llm.patch.yml \
      backend/.venv/bin/python backend/scripts/ab_reddit_dsh_vs_gemini.py --capture 22
    DSH_PATCH_PATH=backend/deploy/dsh/reddit-llm.patch.yml \
      backend/.venv/bin/python backend/scripts/ab_reddit_dsh_vs_gemini.py --replay --repeats 3
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src import config  # noqa: E402
from src.services.reddit_enhanced_service import (  # noqa: E402
    RedditEnhancedService,
    RedditPost,
    get_reddit_enhanced_service,
)
from src.services.dsh_client import get_reddit_llm_client  # noqa: E402

DEFAULT_TELEMETRY = Path("/home/ubuntu/apps/experts-panel/data/reddit_search_telemetry.jsonl")
FIXTURE_DIR = Path(
    os.getenv("AB_REDDIT_FIXTURE_DIR", BACKEND.parent / "output" / "ab_reddit")
)
REPORT_PATH = FIXTURE_DIR / "report.json"


# --- reference set -----------------------------------------------------------


def load_reference(path: Path, limit: int) -> List[Dict[str, Any]]:
    """Most recent unique questions with Gemini's recorded decisions."""
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seen: set[str] = set()
    picked: List[Dict[str, Any]] = []
    for record in reversed(records):
        query = record.get("query")
        if not query or query in seen:
            continue
        seen.add(query)
        picked.append(record)
        if len(picked) >= limit:
            break
    return picked


def reference_winners(record: Dict[str, Any]) -> List[str]:
    return [w["id"] for w in record.get("winners", []) if w.get("id")]


def fixture_path(record: Dict[str, Any]) -> Path:
    key = record.get("plan_query") or record["query"]
    slug = "".join(c if c.isalnum() else "-" for c in key.lower())
    safe = re.sub(r"-+", "-", slug)[:80].strip("-")
    return FIXTURE_DIR / f"{safe}.json"


# --- phase 1: live capture ---------------------------------------------------


async def capture_one(service: RedditEnhancedService, record: Dict[str, Any]) -> Dict[str, Any]:
    """Run one V2 retrieval and freeze the judge candidates."""
    captured: Dict[str, Any] = {}

    async def wrapped(*args, **kwargs):
        # Instance-attribute override: Python does not bind self, so the
        # positional order is the call site's:
        # (candidates, remaining, plan_query, target_posts, include_comments,
        #  anchor_terms, search_plan, original_user_query, must_keep_terms, trace)
        #
        # `candidates` is the heuristic top-N that reaches the judge; the
        # `remaining` tail is what the candidate cut throws away. Both are
        # frozen: without the tail a later experiment cannot ask whether a
        # different cut would have judged better material.
        candidates = args[0] if args else kwargs.get("candidates_for_rerank", [])
        remaining = args[1] if len(args) > 1 else kwargs.get("remaining_posts", [])
        pass_record = {
            "candidates": [dataclasses.asdict(p) for p in candidates],
            "remaining": [dataclasses.asdict(p) for p in remaining],
        }
        captured.setdefault("passes", []).append(pass_record)
        # The FIRST call is the main ranking pass; a later one is the
        # reflection retry, whose much smaller pool must not overwrite it.
        if "candidates" not in captured:
            captured["candidates"] = pass_record["candidates"]
            captured["remaining"] = pass_record["remaining"]
        captured["plan_query"] = args[2] if len(args) > 2 else kwargs.get("plan_query")
        captured["anchor_terms"] = args[5] if len(args) > 5 else kwargs.get("anchor_terms", [])
        captured["search_plan"] = args[6] if len(args) > 6 else kwargs.get("search_plan", {})
        return await original(*args, **kwargs)

    original = service._rank_and_filter
    service._rank_and_filter = wrapped
    try:
        started = time.monotonic()
        result = await service.search_enhanced(
            query=record["plan_query"] or record["query"],
            target_posts=25,
            include_comments=True,
            original_user_query=record["query"],
            user_intent=record.get("intent"),
        )
        elapsed = time.monotonic() - started
    finally:
        service._rank_and_filter = original

    return {
        "query": record["query"],
        "plan_query": record.get("plan_query"),
        "intent": record.get("intent"),
        "gemini_winners": reference_winners(record),
        "gemini_selected": record.get("selected_posts"),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "live_latency_s": round(elapsed, 1),
        "live_selected": [p.id for p in result.posts],
        "live_unique_posts": result.total_found,
        "candidates": captured.get("candidates", []),
        # The tail the candidate cut dropped, plus every ranking pass: without
        # them a later experiment cannot ask what a different cut would have
        # judged (see reddit_rerank_diversity_probe.py).
        "remaining": captured.get("remaining", []),
        "passes": captured.get("passes", []),
        "anchor_terms": captured.get("anchor_terms", []),
        "search_plan": captured.get("search_plan", {}),
    }


async def run_capture(limit: int, telemetry: Path, pause_s: float) -> int:
    records = load_reference(telemetry, limit)
    print(f"reference questions: {len(records)} from {telemetry}")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    service = get_reddit_enhanced_service()
    try:
        for index, record in enumerate(records, 1):
            target = fixture_path(record)
            if target.exists():
                print(f"[{index}/{len(records)}] cached: {target.name}")
                continue
            label = (record.get("plan_query") or record["query"])[:60]
            try:
                fixture = await capture_one(service, record)
            except Exception as exc:
                print(f"[{index}/{len(records)}] FAILED {label}: {exc}")
                continue
            target.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            print(
                f"[{index}/{len(records)}] {label} | "
                f"candidates={len(fixture['candidates'])} "
                f"selected={len(fixture['live_selected'])} "
                f"gemini_winners={len(fixture['gemini_winners'])} "
                f"{fixture['live_latency_s']}s"
            )
            if pause_s:
                await asyncio.sleep(pause_s)
    finally:
        await service.close()
    return 0


# --- phase 2: offline replay -------------------------------------------------


def load_fixtures() -> List[Dict[str, Any]]:
    """Fixtures only: the report files share the directory but not the schema."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIR.glob("*.json"))
        if not path.name.startswith("report")
    ]


async def judge_once(
    service: RedditEnhancedService, fixture: Dict[str, Any]
) -> Dict[str, Any]:
    posts = [RedditPost(**payload) for payload in fixture["candidates"]]
    anchor_terms = fixture.get("anchor_terms") or []
    intent = (fixture.get("search_plan") or {}).get("intent") or fixture.get("intent") or "discussion"

    started = time.monotonic()
    ranked = await service._ai_rerank_posts(
        fixture.get("plan_query") or fixture["query"],
        posts,
        intent=intent,
        anchor_terms=anchor_terms,
        original_user_query=fixture["query"],
    )
    latency = time.monotonic() - started

    # Mirror `_rank_and_filter`: a wholly unrated pool is a disclosed outage,
    # not a relevance verdict. Without this the harness would abstain where
    # the pipeline degrades visibly.
    judge_unavailable = bool(ranked) and all(
        p.evidence_status == "unavailable" for p in ranked
    )
    tier: Dict[str, Any] = {}
    selected = service._apply_confidence_threshold(
        ranked,
        target_posts=25,
        require_anchor_match=bool(anchor_terms),
        intent=intent,
        judge_unavailable=judge_unavailable,
        tier_out=tier,
    )

    statuses = [p.evidence_status for p in ranked]
    verified_ids = [p.id for p in ranked if p.evidence_status == "verified"]
    available = [pid for pid in fixture["gemini_winners"] if pid in {p.id for p in posts}]
    selected_ids = [p.id for p in selected]
    agreed = [pid for pid in available if pid in selected_ids]

    return {
        "query": fixture["query"],
        "intent": intent,
        "candidates": len(posts),
        "judge_latency_s": round(latency, 1),
        "verified": len(verified_ids),
        "verified_rate": round(len(verified_ids) / len(posts), 3) if posts else 0.0,
        "unrated": sum(1 for s in statuses if s == "unavailable"),
        "invalid": sum(1 for s in statuses if s == "invalid_rating"),
        "judge_unavailable": judge_unavailable,
        "decision_tier": tier.get("decision_tier"),
        "selected": selected_ids,
        "selected_count": len(selected_ids),
        "gemini_winners": fixture["gemini_winners"],
        "gemini_selected": fixture.get("gemini_selected"),
        "available": available,
        "agreed": agreed,
        "agreement": round(len(agreed) / len(available), 3) if available else None,
        "top_scores": [
            {"id": p.id, "ai": round(p.ai_score, 3), "final": round(p.final_score, 3),
             "evidence": p.evidence_status}
            for p in ranked[:3]
        ],
        # Full per-post trail: the tuning loop must distinguish "the judge
        # found no quotable span" from "the judge judged it irrelevant".
        "judged": [
            {
                "id": p.id,
                "ai": round(p.ai_score, 3),
                "final": round(p.final_score, 3),
                "evidence": p.evidence_status,
                "reason": (p.ranking_reason or "")[:200],
                "span": (p.evidence_span or "")[:160],
            }
            for p in ranked
        ],
    }


async def run_replay(repeats: int) -> int:
    fixtures = load_fixtures()
    if not fixtures:
        print(f"no fixtures in {FIXTURE_DIR}; run --capture first")
        return 2
    service = object.__new__(RedditEnhancedService)
    service._llm_client = get_reddit_llm_client()

    runs: List[List[Dict[str, Any]]] = []
    for attempt in range(1, repeats + 1):
        print(f"\n=== replay {attempt}/{repeats} ===")
        attempt_rows = []
        for index, fixture in enumerate(fixtures, 1):
            try:
                row = await judge_once(service, fixture)
            except Exception as exc:
                print(f"[{index}/{len(fixtures)}] FAILED: {exc}")
                continue
            attempt_rows.append(row)
            print(
                f"[{index}/{len(fixtures)}] {row['query'][:48]:<48} "
                f"verified={row['verified']}/{row['candidates']} "
                f"sel={row['selected_count']} (gemini {row['gemini_selected']}) "
                f"agree={row['agreement']} {row['judge_latency_s']}s"
            )
        runs.append(attempt_rows)
        # Every attempt judges the same frozen pools; keep them in the report.

    report = summarize(runs)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(report)
    print(f"\nreport: {REPORT_PATH}")
    return 0


def summarize(runs: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    last = runs[-1]
    latencies = [row["judge_latency_s"] for row in last]
    verified_rates = [row["verified_rate"] for row in last]
    agreements = [row["agreement"] for row in last if row["agreement"] is not None]
    drift = [
        len(row["available"]) / len(row["gemini_winners"])
        for row in last
        if row["gemini_winners"]
    ]
    return {
        "questions": len(last),
        "repeats": len(runs),
        "engine": config.REDDIT_LLM_BACKEND,
        "judge_model_note": "dsh: deepseek/deepseek-v4.1-flash via --profile headless",
        "latency_s": {
            "mean": round(statistics.mean(latencies), 1) if latencies else None,
            "p90": round(sorted(latencies)[int(len(latencies) * 0.9) - 1], 1) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "verified_rate_mean": round(statistics.mean(verified_rates), 3) if verified_rates else None,
        "verified_rate_by_run": [
            round(statistics.mean([r["verified_rate"] for r in run]), 3)
            for run in runs
            if run
        ],
        "agreement_mean": round(statistics.mean(agreements), 3) if agreements else None,
        "agreement_by_run": [
            round(statistics.mean([r["agreement"] for r in run if r["agreement"] is not None]), 3)
            for run in runs
            if any(r["agreement"] is not None for r in run)
        ],
        "gemini_winners_still_in_pool": round(statistics.mean(drift), 3) if drift else None,
        "unrated_total": sum(row["unrated"] for row in last),
        "invalid_total": sum(row["invalid"] for row in last),
        "judge_outage_questions": sum(
            1 for row in last if row.get("judge_unavailable")
        ),
        "abstains": sum(1 for row in last if row["selected_count"] == 0),
        "gemini_abstains": sum(1 for row in last if not row["gemini_winners"]),
        "per_question": last,
    }


def print_report(report: Dict[str, Any]) -> None:
    print("\n--- summary ---")
    print(f"questions: {report['questions']} | repeats: {report['repeats']} | engine: {report['engine']}")
    print(f"judge latency: {report['latency_s']}")
    print(f"verified rate by run: {report['verified_rate_by_run']}")
    print(f"agreement with Gemini winners by run: {report['agreement_by_run']}")
    print(f"Gemini winners still in today's pool: {report['gemini_winners_still_in_pool']}")
    print(f"unrated: {report['unrated_total']} | invalid: {report['invalid_total']}")
    print(f"abstains: dsh={report['abstains']} gemini={report['gemini_abstains']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=int, metavar="N", help="capture N live fixtures")
    parser.add_argument("--replay", action="store_true", help="replay the judge on fixtures")
    parser.add_argument("--repeats", type=int, default=1, help="replay passes (variance)")
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY)
    parser.add_argument("--pause", type=float, default=3.0, help="seconds between live searches")
    args = parser.parse_args()

    if args.capture:
        return asyncio.run(run_capture(args.capture, args.telemetry, args.pause))
    if args.replay:
        return asyncio.run(run_replay(args.repeats))
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
