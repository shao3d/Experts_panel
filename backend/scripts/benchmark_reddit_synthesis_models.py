#!/usr/bin/env python3
"""Blind, source-parity benchmark for Reddit synthesis models.

Retrieval runs exactly once per scenario. Every model then receives the same
messages built from that frozen in-memory Reddit corpus. Results are written to
the ignored backend/test_results tree and never change production settings.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, require_vertex_runtime, set_default_sqlite_database_url

BACKEND_DIR, logger = bootstrap_cli(
    __file__, logger_name="cli.benchmark_reddit_synthesis_models"
)
set_default_sqlite_database_url(BACKEND_DIR)

from src.services.reddit_enhanced_service import RedditEnhancedService
from src.services.reddit_synthesis_service import RedditSynthesisService
from src.services.vertex_llm_client import get_vertex_llm_client


MODELS = {
    "gemini": "google/gemini-3-flash-preview",
    "qwen": "qwen/qwen3.8-flash",
    "luna": "openai/gpt-5.6-luna",
    "deepseek": "deepseek/deepseek-v4-flash",
}

SCENARIOS = [
    {
        "id": "troubleshooting_ru",
        "category": "technical troubleshooting",
        "query": "Почему hooks в Claude Code не срабатывают и как это исправляют на практике?",
        "search_query": "Claude Code hooks not working troubleshooting",
    },
    {
        "id": "comparison_ru",
        "category": "direct tool comparison",
        "query": "Cursor или Claude Code: что разработчики выбирают для больших проектов и почему?",
        "search_query": "Cursor vs Claude Code large projects comparison",
    },
    {
        "id": "workflow_ru",
        "category": "practitioner workflow and sentiment",
        "query": "Как разработчики реально используют MCP в ежедневной работе и где он приносит пользу?",
        "search_query": "MCP practical daily workflow coding agents",
    },
    {
        "id": "fresh_numbers_ru",
        "category": "fresh version-sensitive evidence with numbers",
        "query": "Что разработчики пишут о локальном запуске новых Qwen-моделей: требования к VRAM, скорость и основные проблемы?",
        "search_query": "Qwen local inference VRAM speed benchmark problems",
    },
    {
        "id": "weak_signal_en",
        "category": "narrow and potentially weak evidence",
        "query": "Are nested AGENTS.md instructions actually useful in coding-agent projects?",
        "search_query": "nested AGENTS.md instructions coding agents experience",
    },
]

SOURCE_REF_RE = re.compile(r"\[S(\d+)\]", re.IGNORECASE)


def _serialize_post(post: Any) -> dict[str, Any]:
    return {
        "title": post.title,
        "subreddit": post.subreddit,
        "url": post.url or post.permalink,
        "score": post.score,
        "num_comments": post.num_comments,
        "created_utc": post.created_utc,
        "selftext": post.selftext,
        "top_comments": post.top_comments,
        "strategy_hits": post.strategy_hits,
        "ai_score": post.ai_score,
        "heuristic_score": post.heuristic_score,
        "final_score": post.final_score,
    }


def _structural_metrics(text: str, source_count: int, language: str) -> dict[str, Any]:
    refs = [int(value) for value in SOURCE_REF_RE.findall(text)]
    invalid_refs = sorted({value for value in refs if value < 1 or value > source_count})
    if language == "Russian":
        section_groups = [
            ("summary", ["executive summary", "краткий вывод", "резюме"]),
            ("deep_dive", ["deep dive", "подроб", "детальн"]),
            ("minority", ["minority report", "альтернатив", "меньшинств"]),
            ("edge_cases", ["edge case", "граничн", "подводн", "реальные проблемы"]),
            ("actions", ["куда иди", "что делать", "рекомендац"]),
        ]
    else:
        section_groups = [
            ("summary", ["executive summary", "summary"]),
            ("deep_dive", ["deep dive"]),
            ("minority", ["minority report"]),
            ("edge_cases", ["edge case"]),
            ("actions", ["where to go", "recommendation", "next steps"]),
        ]
    lowered = text.lower()
    sections = {
        name: any(marker in lowered for marker in markers)
        for name, markers in section_groups
    }
    return {
        "chars": len(text),
        "words": len(text.split()),
        "source_ref_mentions": len(refs),
        "unique_source_refs": len(set(refs)),
        "invalid_source_refs": invalid_refs,
        "sections": sections,
        "section_coverage": sum(sections.values()),
    }


async def _model_prices() -> dict[str, dict[str, float]]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
    wanted = set(MODELS.values())
    prices: dict[str, dict[str, float]] = {}
    for item in response.json().get("data", []):
        if item.get("id") not in wanted:
            continue
        pricing = item.get("pricing") or {}
        prices[item["id"]] = {
            "prompt": float(pricing.get("prompt") or 0),
            "completion": float(pricing.get("completion") or 0),
        }
    return prices


async def _run_model(
    *,
    label: str,
    model: str,
    messages: list[dict[str, str]],
    prices: dict[str, dict[str, float]],
    max_tokens: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    client = get_vertex_llm_client()
    started = time.perf_counter()
    # Use the common parameter intersection. Luna does not expose temperature,
    # so sending it would make provider.require_parameters reject an otherwise
    # fair request before generation starts.
    payload = await asyncio.wait_for(
        client._post(
            {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "reasoning": {"enabled": False},
                "provider": {"require_parameters": True},
            }
        ),
        timeout=timeout_seconds,
    )
    latency = time.perf_counter() - started
    choice = payload["choices"][0]
    text = (choice.get("message") or {}).get("content") or ""
    text = text.strip()
    if not text:
        raise RuntimeError("model returned no textual answer")
    usage = payload.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    price = prices.get(model, {"prompt": 0.0, "completion": 0.0})
    estimated_cost = (
        prompt_tokens * price["prompt"] + completion_tokens * price["completion"]
    )
    return {
        "label": label,
        "requested_model": model,
        "served_model": payload.get("model") or model,
        "finish_reason": choice.get("finish_reason") or "unknown",
        "latency_seconds": round(latency, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": round(estimated_cost, 8),
        "answer": text,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-tokens", type=int, default=2500)
    parser.add_argument("--model-timeout", type=float, default=120.0)
    parser.add_argument("--scenario", action="append", help="Run only matching scenario id")
    args = parser.parse_args()
    require_vertex_runtime()

    selected = [
        item for item in SCENARIOS if not args.scenario or item["id"] in args.scenario
    ]
    if not selected:
        raise SystemExit("No scenarios selected")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or (
        BACKEND_DIR / "test_results" / "reddit_synthesis_models" / run_id
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    prices = await _model_prices()
    if set(prices) != set(MODELS.values()):
        raise SystemExit("OpenRouter pricing snapshot is incomplete")

    synthesis = RedditSynthesisService()
    retrieval = RedditEnhancedService()
    rng = random.Random(20260901)
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "max_tokens": args.max_tokens,
        "model_timeout_seconds": args.model_timeout,
        "models": MODELS,
        "prices_per_token": prices,
        "scenarios": [],
    }

    try:
        for index, scenario in enumerate(selected, start=1):
            print(f"[{index}/{len(selected)}] retrieval: {scenario['id']}", flush=True)
            result = await retrieval.search_enhanced(
                query=scenario["search_query"],
                target_posts=10,
                include_comments=True,
            )
            if not result.posts:
                raise RuntimeError(f"No synthesis corpus for {scenario['id']}")
            context = synthesis._build_context(result, max_sources=10)
            language = "Russian" if scenario["id"].endswith("_ru") else "English"
            messages = synthesis._create_synthesis_prompt(
                scenario["query"], context, language
            )
            corpus = [_serialize_post(post) for post in result.posts[:10]]

            order = list(MODELS.items())
            rng.shuffle(order)
            scenario_path = output_dir / f"{scenario['id']}.json"
            scenario_payload = {
                **scenario,
                "language": language,
                "retrieval": {
                    "processing_time_ms": result.processing_time_ms,
                    "total_found": result.total_found,
                    "strategies_used": result.strategies_used,
                    "source_count": len(corpus),
                },
                "corpus": corpus,
                "runs": [],
            }
            scenario_path.write_text(
                json.dumps(scenario_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            for model_index, (label, model) in enumerate(order, start=1):
                print(
                    f"  [{model_index}/{len(order)}] synthesis: {label}", flush=True
                )
                try:
                    run = await _run_model(
                        label=label,
                        model=model,
                        messages=messages,
                        prices=prices,
                        max_tokens=args.max_tokens,
                        timeout_seconds=args.model_timeout,
                    )
                    run["metrics"] = _structural_metrics(
                        run["answer"], len(corpus), language
                    )
                    run["error"] = None
                except Exception as exc:
                    run = {
                        "label": label,
                        "requested_model": model,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                scenario_payload["runs"].append(run)
                scenario_path.write_text(
                    json.dumps(scenario_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            manifest["scenarios"].append(
                {
                    "id": scenario["id"],
                    "file": scenario_path.name,
                    "source_count": len(corpus),
                    "completed_models": sum(
                        not run.get("error") for run in scenario_payload["runs"]
                    ),
                }
            )
    finally:
        await retrieval.close()

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Benchmark complete: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
