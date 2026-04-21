#!/usr/bin/env python3
"""Evaluate Reddit Search V2 on representative AI/productivity queries."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (
    bootstrap_cli,
    require_vertex_runtime,
    set_default_sqlite_database_url,
)

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.eval_reddit_search_v2",
)
set_default_sqlite_database_url(BACKEND_DIR)

from src.services.reddit_enhanced_service import RedditEnhancedService


EVAL_QUERIES: List[Tuple[str, str]] = [
    ("How-to", "Claude Code MCP server setup"),
    ("How-to", "RAG chunking strategy production"),
    ("How-to", "best system prompts AI coding"),
    ("Troubleshooting", "CUDA out of memory LLM fix"),
    ("Troubleshooting", "slow token generation troubleshooting"),
    ("Comparison", "Cursor vs Claude Code comparison"),
    ("Comparison", "llama.cpp vs ollama performance"),
    ("Comparison", "vLLM TGI inference engine comparison"),
    ("Best practices", "reduce AI hallucinations in production systems"),
    ("Best practices", "structured output JSON schema LLM"),
    ("Infra", "nginx reverse proxy ollama"),
    ("Infra", "air gapped offline AI deployment"),
]


def _result_to_dict(category: str, query: str, result) -> Dict[str, Any]:
    top_posts = []
    for post in result.posts[:5]:
        top_posts.append(
            {
                "id": post.id,
                "title": post.title,
                "subreddit": post.subreddit,
                "score": post.score,
                "num_comments": post.num_comments,
                "heuristic_score": round(post.heuristic_score, 3),
                "ai_score": round(post.ai_score, 3),
                "final_score": round(post.final_score, 3),
                "strategy_hits": post.strategy_hits,
                "ranking_reason": post.ranking_reason,
                "url": post.permalink or post.url,
            }
        )

    return {
        "category": category,
        "query": query,
        "total_found": result.total_found,
        "returned_posts": len(result.posts),
        "strategies_used": result.strategies_used,
        "processing_time_ms": result.processing_time_ms,
        "debug_trace": result.debug_trace,
        "top_posts": top_posts,
    }


async def _run_query(
    service: RedditEnhancedService, category: str, query: str
) -> Dict[str, Any]:
    result = await service.search_enhanced(
        query=query,
        target_posts=8,
        include_comments=True,
    )
    return _result_to_dict(category, query, result)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        help="Run a single ad-hoc query instead of the built-in benchmark set",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write full JSON results",
    )
    args = parser.parse_args()
    require_vertex_runtime()

    query_set = (
        [("AdHoc", args.query.strip())]
        if args.query and args.query.strip()
        else EVAL_QUERIES
    )

    service = RedditEnhancedService()
    try:
        results: List[Dict[str, Any]] = []
        for idx, (category, query) in enumerate(query_set, start=1):
            print(f"\n[{idx}/{len(query_set)}] {category}: {query}")
            result = await _run_query(service, category, query)
            results.append(result)

            print(
                f"  total_found={result['total_found']} "
                f"returned={result['returned_posts']} "
                f"time={result['processing_time_ms']}ms"
            )
            print(f"  strategies={', '.join(result['strategies_used'])}")

            if not result["top_posts"]:
                print("  no high-confidence posts returned")
                continue

            for post_idx, post in enumerate(result["top_posts"], start=1):
                print(
                    f"  {post_idx}. r/{post['subreddit']} "
                    f"[final={post['final_score']}, ai={post['ai_score']}] "
                    f"{post['title'][:120]}"
                )

        if results:
            returned_total = sum(item["returned_posts"] for item in results)
            avg_returned = returned_total / len(results)
            avg_time_ms = sum(item["processing_time_ms"] for item in results) / len(results)
            empty_queries = [
                item["query"] for item in results if item["returned_posts"] == 0
            ]
            thin_queries = [
                item["query"] for item in results if 0 < item["returned_posts"] < 3
            ]

            print("\n=== Summary ===")
            print(f"queries={len(results)}")
            print(f"returned_total={returned_total}")
            print(f"avg_returned={avg_returned:.2f}")
            print(f"avg_time_ms={avg_time_ms:.1f}")
            print(f"empty_queries={len(empty_queries)}")
            if empty_queries:
                print("  " + "; ".join(empty_queries))
            print(f"thin_queries={len(thin_queries)}")
            if thin_queries:
                print("  " + "; ".join(thin_queries))

        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
            print(f"\nSaved JSON results to {output_path}")

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
