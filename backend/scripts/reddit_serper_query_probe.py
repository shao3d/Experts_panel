#!/usr/bin/env python
"""Measure Serper (Google `site:reddit.com`) query formulations, judge-free.

Today `_search_serper` sends the compact plan query verbatim:

    q = "GLM-5.3 Flash latency DeepSeek V4.1 Flash agentic coding site:reddit.com"

Google — unlike Reddit's OR-ish relevance search — honours quotes, so the
hypothesis is that naming the compared products (optionally quoted) buys
precision the same way `comparison_entity_pair` did for the native channel
(see reddit_comparison_entities_probe.py, roadmap 0.6).

Metrics per arm (identical to the native probe, so numbers are comparable):

* ``both_entities`` — returned Reddit results mentioning BOTH compared things
  in title+snippet, plus how many carry an explicit comparison marker.
* ``winners_found`` — posts the live pipeline actually selected for that
  question (telemetry), i.e. would this formulation have reached the material
  the answer used.

Costs one Serper credit per arm per question (num <= 10 stays in one credit).

Usage (from backend/; the key is read from SERPER_API_KEY, never printed):
    SERPER_API_KEY=... .venv/bin/python -u \
        scripts/reddit_serper_query_probe.py --questions 10 --out ../output/ab_reddit/serper_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reddit_comparison_entities_probe import (  # noqa: E402
    _has_marker,
    _load_questions,
    _mentions,
)
from src import config  # noqa: E402
from src.services.reddit_enhanced_service import _extract_comparison_entities  # noqa: E402

DEFAULT_OUT = BACKEND.parent / "output" / "ab_reddit" / "serper_query_report.json"
_ID_RE = re.compile(r"/comments/([a-z0-9]+)/", re.IGNORECASE)


def _arm_queries(question: Dict[str, Any]) -> Dict[str, str]:
    """Query strings WITHOUT the site: filter (added per request)."""
    entities = _extract_comparison_entities(question["query"])
    arms = {"plan": question["plan_query"]}
    if len(entities) >= 2:
        pair = f"{entities[0]} {entities[1]}"
        arms["entity"] = " ".join(entities[:3])
        arms["entity_quoted"] = f'"{entities[0]}" "{entities[1]}"'
        arms["entity_vs"] = f"{entities[0]} vs {entities[1]}"
        # Does the plan wording add anything on top of the pair, or does it
        # only narrow the query ("agentic coding")?
        arms["combined"] = f"{entities[0]} vs {entities[1]} {question['plan_query']}"
    return arms


async def _serper(
    client: httpx.AsyncClient, query: str, num: int
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    payload = {"q": f"{query} site:reddit.com", "num": num}
    try:
        resp = await client.post(
            config.SERPER_ENDPOINT,
            json=payload,
            headers={"X-API-KEY": os.environ["SERPER_API_KEY"]},
        )
    except Exception as exc:  # noqa: BLE001 - a probe must survive one bad arm
        return [], f"transport: {exc}"
    if resp.status_code != 200:
        return [], f"HTTP {resp.status_code}: {resp.text[:120]}"
    return (resp.json() or {}).get("organic") or [], None


def _reddit_results(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Only post permalinks; the backend channel drops everything else too."""
    out: List[Dict[str, Any]] = []
    for item in items:
        link = item.get("link") or ""
        match = _ID_RE.search(link)
        if not match:
            continue
        out.append(
            {
                "id": match.group(1),
                "url": link,
                "title": item.get("title") or "",
                "snippet": item.get("snippet") or "",
                "position": item.get("position"),
            }
        )
    return out


async def run(args: argparse.Namespace, out_path: Path) -> int:
    if not os.environ.get("SERPER_API_KEY"):
        raise SystemExit("SERPER_API_KEY is not set in this process environment")

    questions = _load_questions(args.questions)
    if not questions:
        raise SystemExit("no comparison questions with a reference mapping found")

    report: Dict[str, Any] = {
        "endpoint": config.SERPER_ENDPOINT,
        "num": args.num,
        "questions": [],
    }
    totals: Dict[str, Dict[str, float]] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        for index, question in enumerate(questions, start=1):
            arms = _arm_queries(question)
            print(f"\n[{index}/{len(questions)}] {question['query'][:84]}")
            entry: Dict[str, Any] = {
                "query": question["query"],
                "plan_query": question["plan_query"],
                "reference": question["reference"],
                "winner_ids": question["winner_ids"],
                "arms": {},
            }
            ids_by_arm: Dict[str, set] = {}
            for arm, query in arms.items():
                items, error = await _serper(client, query, args.num)
                results = _reddit_results(items)
                ids_by_arm[arm] = {r["id"] for r in results}
                entry["arms"][arm] = {"query": query, "error": error, "results": results}
                await asyncio.sleep(args.pause)

            winner_ids = set(question["winner_ids"])
            for arm, payload in entry["arms"].items():
                results = payload["results"]
                both = [
                    r
                    for r in results
                    if _mentions(f"{r['title']} {r['snippet']}", question["reference"]) >= 2
                ]
                both_marked = [
                    r for r in both if _has_marker(f"{r['title']} {r['snippet']}")
                ]
                found = sorted(ids_by_arm[arm] & winner_ids)
                unique = [
                    r["id"]
                    for r in results
                    if not any(
                        r["id"] in ids_by_arm[other]
                        for other in ids_by_arm
                        if other != arm
                    )
                ]
                payload.update(
                    {
                        "returned": len(results),
                        "both_entities": len(both),
                        "both_entities_marked": len(both_marked),
                        "winners_found": found,
                        "unique": unique,
                    }
                )
                agg = totals.setdefault(
                    arm,
                    {"returned": 0.0, "both": 0.0, "marked": 0.0, "winners": 0.0, "errors": 0.0},
                )
                agg["returned"] += len(results)
                agg["both"] += len(both)
                agg["marked"] += len(both_marked)
                agg["winners"] += len(found)
                agg["errors"] += 1 if payload["error"] else 0
                print(
                    f"    {arm:14s} q={payload['query'][:58]!r} -> {len(results):2d} reddit "
                    f"| both-entity {len(both):2d} (marked {len(both_marked):2d}) "
                    f"| winners {len(found)}/{len(winner_ids)}"
                    + (f" | {payload['error']}" if payload["error"] else "")
                )

            report["questions"].append(entry)
            report["totals"] = totals
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== totals ===")
    print(f"{'arm':16s} {'reddit':>7s} {'both':>6s} {'marked':>7s} {'winners':>8s} {'errors':>7s}")
    for arm, agg in sorted(totals.items()):
        print(
            f"{arm:16s} {int(agg['returned']):7d} {int(agg['both']):6d} "
            f"{int(agg['marked']):7d} {int(agg['winners']):8d} {int(agg['errors']):7d}"
        )
    print(f"\nreport: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=int, default=10, help="how many questions to probe")
    parser.add_argument("--num", type=int, default=8, help="results per query (production uses SERPER_RESULTS=8)")
    parser.add_argument("--pause", type=float, default=0.6, help="seconds between requests")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report path")
    args = parser.parse_args()
    return asyncio.run(run(args, Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
