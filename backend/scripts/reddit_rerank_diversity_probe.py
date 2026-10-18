#!/usr/bin/env python3
"""Does the candidate cut throw away material the judge would have kept?

The pipeline ranks every unique candidate heuristically and sends only
`REDDIT_RERANK_CANDIDATES` of them (18 by default) to the answerability judge.
Measured on the owner's searches: the median pool holds 134 unique candidates,
so the cut — not the judge — decides what an answer can possibly rest on. The
heuristic score rewards anchor-word overlap, which lets one strategy or one
subreddit take the whole slate.

This probe takes frozen FULL pools (the judged top plus the dropped tail, see
`ab_reddit_dsh_vs_gemini.py --capture`), builds two slates from the same pool —

    plain     the heuristic top-N, i.e. today's behaviour
    diverse   N - slots heuristic + `slots` best posts from strategies and
              subreddits the top does not cover (`_split_rerank_candidates`)

— runs the SAME judge on both, applies the same confidence/evidence gate, and
reports what each slate yields. Nothing is written to production paths.

Usage:
    REDDIT_PROXY_URL=http://localhost:3000 \
    DSH_PATCH_PATH=backend/deploy/dsh/reddit-llm.patch.yml \
      backend/.venv/bin/python backend/scripts/reddit_rerank_diversity_probe.py \
        --fixtures output/ab_reddit_full --slots 4
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
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src import config  # noqa: E402
from src.services.reddit_enhanced_service import (  # noqa: E402
    RedditEnhancedService,
    RedditPost,
)
from src.services.dsh_client import get_reddit_llm_client  # noqa: E402

RESULTS_DIR = BACKEND.parent / "output" / "ab_reddit"
REPORT_PATH = RESULTS_DIR / "rerank_diversity_report.json"


def load_pools(fixtures_dir: Path, limit: int = 0) -> List[Dict[str, Any]]:
    pools = []
    for path in sorted(fixtures_dir.glob("*.json")):
        if path.name.startswith("report"):
            continue
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        cand = [RedditPost(**p) for p in fixture.get("candidates") or []]
        tail = [RedditPost(**p) for p in fixture.get("remaining") or []]
        if not cand:
            continue
        pools.append(
            {
                "query": fixture["query"],
                "plan_query": fixture.get("plan_query") or fixture["query"],
                "intent": (fixture.get("search_plan") or {}).get("intent")
                or fixture.get("intent")
                or "discussion",
                "anchor_terms": fixture.get("anchor_terms") or [],
                "pool": cand + tail,
            }
        )
    return pools[:limit] if limit else pools


def fresh(posts: List[RedditPost]) -> List[RedditPost]:
    """Copy so the two judge runs cannot contaminate each other."""
    return [RedditPost(**dataclasses.asdict(p)) for p in posts]


async def judge(
    service: RedditEnhancedService, row: Dict[str, Any], slate: List[RedditPost]
) -> Dict[str, Any]:
    posts = fresh(slate)
    started = time.monotonic()
    ranked = await service._ai_rerank_posts(
        row["plan_query"],
        posts,
        intent=row["intent"],
        anchor_terms=row["anchor_terms"],
        original_user_query=row["query"],
    )
    latency = time.monotonic() - started
    judge_unavailable = bool(ranked) and all(
        p.evidence_status == "unavailable" for p in ranked
    )
    tier: Dict[str, Any] = {}
    selected = service._apply_confidence_threshold(
        ranked,
        target_posts=25,
        require_anchor_match=bool(row["anchor_terms"]),
        intent=row["intent"],
        judge_unavailable=judge_unavailable,
        tier_out=tier,
    )
    return {
        "latency_s": round(latency, 1),
        "judged": [p.id for p in ranked],
        "selected": [p.id for p in selected],
        "selected_detail": [
            {
                "id": p.id,
                "strategy": p.found_by_strategy,
                "subreddit": p.subreddit,
                "ai": round(p.ai_score, 3),
                "final": round(p.final_score, 3),
                "evidence": p.evidence_status,
            }
            for p in selected
        ],
        "strategies_judged": sorted(
            {p.found_by_strategy for p in ranked if p.found_by_strategy}
        ),
        "subreddits_judged": sorted({p.subreddit for p in ranked if p.subreddit}),
        "strategies_selected": sorted(
            {p.found_by_strategy for p in selected if p.found_by_strategy}
        ),
        "subreddits_selected": sorted({p.subreddit for p in selected if p.subreddit}),
        "verified": sum(
            1
            for p in selected
            if p.evidence_status in config.EVIDENCE_GATE_ALLOWED_STATUSES
        ),
        "tier": tier.get("decision_tier"),
        "judge_unavailable": judge_unavailable,
    }


async def run(fixtures_dir: Path, slots: int, limit: int, alt_size: int = 0) -> int:
    pools = load_pools(fixtures_dir, limit)
    if not pools:
        print(f"no fixtures with a candidate pool in {fixtures_dir}")
        return 1
    service = object.__new__(RedditEnhancedService)
    service._llm_client = get_reddit_llm_client()

    rows = []
    for index, row in enumerate(pools, 1):
        pool = row["pool"]
        plain_slate = pool[: config.REDDIT_RERANK_CANDIDATES]
        diverse_slate, _ = service._split_rerank_candidates(
            pool, limit=config.REDDIT_RERANK_CANDIDATES, reserved=slots
        )
        print(
            f"[{index}/{len(pools)}] pool={len(pool)} plain={len(plain_slate)} "
            f"diverse={len(diverse_slate)} | {row['query'][:48]}"
        )
        plain = await judge(service, row, plain_slate)
        diverse = await judge(service, row, diverse_slate)
        bigger = None
        if alt_size:
            bigger = await judge(service, row, pool[:alt_size])
        rescued = [p for p in diverse["selected"] if p not in plain["selected"]]
        hidden = [p for p in plain["selected"] if p not in diverse["selected"]]
        row_result = {
            "query": row["query"],
            "pool": len(pool),
            "plain": plain,
            "diverse": diverse,
            "bigger": bigger,
            "selected_only_diverse": rescued,
            "selected_only_plain": hidden,
        }
        rows.append(row_result)
        line = (
            f"    plain: tier={plain['tier']} selected={len(plain['selected'])} "
            f"strategies={len(plain['strategies_selected'])} verified={plain['verified']} "
            f"({plain['latency_s']}s) | diverse: tier={diverse['tier']} "
            f"selected={len(diverse['selected'])} "
            f"strategies={len(diverse['strategies_selected'])} "
            f"verified={diverse['verified']} ({diverse['latency_s']}s) | "
            f"only-diverse={len(rescued)} only-plain={len(hidden)}"
        )
        if bigger:
            line += (
                f" || top-{alt_size}: tier={bigger['tier']} "
                f"selected={len(bigger['selected'])} "
                f"verified={bigger['verified']} ({bigger['latency_s']}s)"
            )
        print(line)

    verdicts = {
        "questions": len(rows),
        "slots": slots,
        "alt_size": alt_size,
        "plain_selected": sum(len(r["plain"]["selected"]) for r in rows),
        "diverse_selected": sum(len(r["diverse"]["selected"]) for r in rows),
        "plain_verified": sum(r["plain"]["verified"] for r in rows),
        "diverse_verified": sum(r["diverse"]["verified"] for r in rows),
        "bigger_selected": sum(
            len(r["bigger"]["selected"]) for r in rows if r.get("bigger")
        ),
        "bigger_verified": sum(r["bigger"]["verified"] for r in rows if r.get("bigger")),
        "selected_only_diverse": sum(len(r["selected_only_diverse"]) for r in rows),
        "selected_only_plain": sum(len(r["selected_only_plain"]) for r in rows),
        "questions_with_new_material": sum(
            1 for r in rows if r["selected_only_diverse"]
        ),
        "plain_strategy_coverage": [
            len(r["plain"]["strategies_judged"]) for r in rows
        ],
        "diverse_strategy_coverage": [
            len(r["diverse"]["strategies_judged"]) for r in rows
        ],
        "latency_median_s": round(
            statistics.median(
                [r["plain"]["latency_s"] for r in rows]
                + [r["diverse"]["latency_s"] for r in rows]
            ),
            1,
        ),
        "per_question": rows,
    }
    REPORT_PATH.write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n--- summary ---")
    print(
        f"questions={verdicts['questions']} slots={slots} | "
        f"selected plain={verdicts['plain_selected']} vs diverse={verdicts['diverse_selected']} | "
        f"verified plain={verdicts['plain_verified']} vs diverse={verdicts['diverse_verified']}"
    )
    print(
        f"new material in the diverse slate: {verdicts['selected_only_diverse']} posts "
        f"on {verdicts['questions_with_new_material']} questions | "
        f"lost from the plain slate: {verdicts['selected_only_plain']}"
    )
    print(
        f"strategy coverage per question: plain median "
        f"{statistics.median(verdicts['plain_strategy_coverage'])} vs diverse median "
        f"{statistics.median(verdicts['diverse_strategy_coverage'])}"
    )
    if alt_size:
        print(
            f"top-{alt_size} slate: selected={verdicts['bigger_selected']} "
            f"vs top-{config.REDDIT_RERANK_CANDIDATES}={verdicts['plain_selected']} | "
            f"verified={verdicts['bigger_verified']} vs {verdicts['plain_verified']}"
        )
    print(f"judge latency median: {verdicts['latency_median_s']}s")
    print(f"written: {REPORT_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=BACKEND.parent / "output" / "ab_reddit_full",
    )
    parser.add_argument("--slots", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--alt-size",
        type=int,
        default=0,
        help="also judge the plain heuristic top-N and compare (0 = off)",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.fixtures, args.slots, args.limit, args.alt_size))


if __name__ == "__main__":
    sys.exit(main())
