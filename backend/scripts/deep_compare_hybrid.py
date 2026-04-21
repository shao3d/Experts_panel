#!/usr/bin/env python3
"""
===========================================================================
Deep Compare: OLD vs HYBRID — полное сравнение ФИНАЛЬНЫХ ОТВЕТОВ
===========================================================================

ЦЕЛЬ:
    Сравнить качество ФИНАЛЬНЫХ ответов (после Map → Resolve → Reduce)
    при двух режимах retrieval:
    - OLD: ВСЕ посты эксперта → Map → Resolve → Reduce
    - HYBRID: Vector+FTS5+RRF → Map → Resolve → Reduce

АРХИТЕКТУРА ПАЙПЛАЙНА (из simplified_query_endpoint.py):
    1. Retrieval → получить посты (OLD=все, HYBRID=отфильтрованные)
    2. Map Phase → LLM классифицирует каждый пост: HIGH / MEDIUM / LOW
    3. HIGH → Resolve (добавляет linked posts как CONTEXT)
    4. MEDIUM → включаются напрямую (MediumScoring пропущен для скорости)
    5. Enriched posts (HIGH+CONTEXT + MEDIUM) → Reduce
    6. Reduce → LLM синтезирует финальный ответ с цитатами [post:ID]

МЕТРИКИ СРАВНЕНИЯ:
    - Текст финального ответа (OLD vs HYBRID)
    - Количество цитированных источников (main_sources)
    - Confidence level, Latency
    - Overlap источников между OLD и HYBRID

ИСПОЛЬЗОВАНИЕ:
    # Быстрый тест (1 запрос × 1 эксперт, ~5 мин):
    python backend/scripts/deep_compare_hybrid.py --query "Как работать со Skills?" --experts doronin

    # Полный тест (3 запроса × 2 эксперта, ~20-30 мин):
    python backend/scripts/deep_compare_hybrid.py --experts doronin akimov

РЕЗУЛЬТАТ:
    deep_compare_hybrid_results.json — оба полных ответа для визуального сравнения.

    ДЛЯ AI-КОДЕРА: открой JSON и сравни old.answer vs hybrid.answer:
    1. Покрывает ли HYBRID те же темы что OLD?
    2. Не потерялись ли ключевые инсайты?
    3. Сколько main_sources пересекается?

ОГРАНИЧЕНИЯ:
    - MediumScoring пропущен (одинаково для обоих → fair comparison)
    - LanguageValidation пропущена (не влияет на retrieval quality)
===========================================================================
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (
    bootstrap_cli,
    require_vertex_runtime,
    set_default_sqlite_database_url,
)

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.deep_compare_hybrid",
)
DB_PATH = set_default_sqlite_database_url(BACKEND_DIR, force=True)

from sqlalchemy import func
from src.models.base import SessionLocal
from src.models.post import Post
from src.services.map_service import MapService
from src.services.simple_resolve_service import SimpleResolveService
from src.services.reduce_service import ReduceService
from src.services.hybrid_retrieval_service import HybridRetrievalService
from src.services.ai_scout_service import AIScoutService
from src.config import MODEL_MAP, MAP_CHUNK_SIZE, MAP_MAX_PARALLEL

# ANSI colors
G = '\033[92m'
Y = '\033[93m'
R = '\033[91m'
B = '\033[94m'
C = '\033[96m'
BOLD = '\033[1m'
DIM = '\033[2m'
RST = '\033[0m'

# ─── Preset test queries ───
DEFAULT_QUERIES = [
    "Как работать со Skills в AI агентах?",
    "Как оптимизировать контекстное окно для длинных документов?",
    "Можно ли доверять AI в принятии бизнес-решений?",
]


def get_all_posts(db, expert_id: str):
    """OLD pipeline: ALL text posts for an expert."""
    return (
        db.query(Post)
        .filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30,
        )
        .order_by(Post.created_at.desc())
        .all()
    )


def extract_map_results(map_result: dict):
    """Split Map Phase output into HIGH and MEDIUM."""
    relevant = map_result.get("relevant_posts", [])
    high = [p for p in relevant if p.get("relevance") == "HIGH"]
    medium = [p for p in relevant if p.get("relevance") == "MEDIUM"]
    return high, medium


async def run_full_pipeline(posts, query: str, expert_id: str, label: str) -> dict:
    """Run FULL pipeline: Map → Resolve → Reduce.

    Replicates simplified_query_endpoint.py process_expert_pipeline().
    MediumScoring skipped for speed (same for both OLD and HYBRID = fair).
    """
    t0 = time.time()
    timings = {}

    # posts_by_id from INPUT posts (matches endpoint: line 348)
    posts_by_id = {p.telegram_message_id: p for p in posts}

    # ── Map Phase ──
    t_map = time.time()
    map_service = MapService(
        model=MODEL_MAP, chunk_size=MAP_CHUNK_SIZE, max_parallel=MAP_MAX_PARALLEL,
    )
    map_result = await map_service.process(
        posts=posts, query=query, expert_id=expert_id,
    )
    high_posts, medium_posts = extract_map_results(map_result)
    timings["map_s"] = round(time.time() - t_map, 1)

    # ── Resolve Phase (HIGH only) ──
    t_resolve = time.time()
    enriched_posts = []
    if high_posts:
        resolve_service = SimpleResolveService()
        resolve_result = await resolve_service.process(
            relevant_posts=high_posts, query=query, expert_id=expert_id,
        )
        enriched_posts.extend(resolve_result.get("enriched_posts", []))
    timings["resolve_s"] = round(time.time() - t_resolve, 1)

    # ── MEDIUM posts direct (skip scoring) ──
    for p in medium_posts:
        pid = p["telegram_message_id"]
        if pid in posts_by_id:
            full_post = posts_by_id[pid]
            enriched_posts.append({
                "telegram_message_id": pid,
                "relevance": "MEDIUM",
                "reason": p.get("reason", ""),
                "content": full_post.message_text or "",
                "author": full_post.author_name or "Unknown",
                "created_at": full_post.created_at.isoformat() if full_post.created_at else "",
                "is_original": True,
            })

    # ── Sort (same as endpoint lines 470-475) ──
    enriched_posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    rel_priority = {"HIGH": 0, "MEDIUM": 1, "CONTEXT": 2}
    enriched_posts.sort(key=lambda x: rel_priority.get(x.get("relevance", "LOW"), 3))

    # ── Reduce Phase ──
    t_reduce = time.time()
    if enriched_posts:
        reduce_service = ReduceService()
        reduce_result = await reduce_service.process(
            enriched_posts=enriched_posts, query=query, expert_id=expert_id,
        )
    else:
        reduce_result = {
            "answer": "Нет релевантных постов.",
            "main_sources": [], "confidence": "LOW", "posts_analyzed": 0,
        }
    timings["reduce_s"] = round(time.time() - t_reduce, 1)
    timings["total_s"] = round(time.time() - t0, 1)

    print(f"    [{label}] Map={timings['map_s']}s Resolve={timings['resolve_s']}s "
          f"Reduce={timings['reduce_s']}s Total={timings['total_s']}s")

    return {
        "answer": reduce_result.get("answer", ""),
        "main_sources": reduce_result.get("main_sources", []),
        "confidence": reduce_result.get("confidence", "MEDIUM"),
        "posts_analyzed": reduce_result.get("posts_analyzed", 0),
        "high_count": len(high_posts),
        "medium_count": len(medium_posts),
        "enriched_count": len(enriched_posts),
        "time_s": round(time.time() - t0, 1),
        "input_posts": len(posts),
        "timings": timings,
    }


async def run_one_query(query: str, expert_ids: list, db) -> dict:
    """Run OLD vs HYBRID full pipeline for one query across all experts."""
    print(f"\n{BOLD}{B}{'=' * 70}{RST}")
    print(f"{BOLD}{B}  Query: {C}{query}{RST}")
    print(f"{BOLD}{B}{'=' * 70}{RST}")

    # AI Scout query (shared)
    print(f"{Y}⏳ AI Scout...{RST}")
    scout = AIScoutService()
    scout_query, scout_ok = await scout.generate_match_query(query)
    print(f"  Scout: {C}{scout_query[:80]}...{RST} ({'✅' if scout_ok else '⚠️'})\n")

    all_results = []

    for expert_id in expert_ids:
        print(f"\n{BOLD}{C}{'─' * 70}{RST}")
        print(f"{BOLD}{C}  Expert: {expert_id}{RST}")
        print(f"{C}{'─' * 70}{RST}")

        all_posts = get_all_posts(db, expert_id)

        # ── OLD ──
        print(f"\n  {Y}▶ OLD ({len(all_posts)} posts → Map → Resolve → Reduce){RST}")
        old_result = await run_full_pipeline(
            posts=all_posts, query=query, expert_id=expert_id, label="OLD",
        )
        print(f"    HIGH:{old_result['high_count']} MED:{old_result['medium_count']} "
              f"→ {old_result['enriched_count']} enriched | "
              f"Sources: {len(old_result['main_sources'])} | {old_result['confidence']}")

        # ── HYBRID ──
        print(f"\n  {Y}▶ HYBRID (Vector+FTS5+RRF → Map → Resolve → Reduce){RST}")
        t_retrieval = time.time()
        hybrid_service = HybridRetrievalService(db)
        hybrid_posts, hybrid_stats = await hybrid_service.search_posts(
            expert_id=expert_id, query=query, match_query=scout_query,
        )
        retrieval_s = round(time.time() - t_retrieval, 1)
        mode = hybrid_stats.get("mode", "?")
        print(f"    Retrieval: {C}{mode}{RST} | "
              f"Vec:{hybrid_stats.get('vector_count', 0)} "
              f"FTS5:{hybrid_stats.get('fts5_count', 0)} "
              f"Overlap:{hybrid_stats.get('overlap', 0)} "
              f"→ {len(hybrid_posts)} posts | ⏱ {retrieval_s}s")

        hybrid_result = await run_full_pipeline(
            posts=hybrid_posts, query=query, expert_id=expert_id, label="HYB",
        )
        print(f"    HIGH:{hybrid_result['high_count']} MED:{hybrid_result['medium_count']} "
              f"→ {hybrid_result['enriched_count']} enriched | "
              f"Sources: {len(hybrid_result['main_sources'])} | {hybrid_result['confidence']}")

        # ── Compare ──
        old_src = set(old_result["main_sources"])
        hyb_src = set(hybrid_result["main_sources"])
        src_overlap = len(old_src & hyb_src)

        print(f"\n  {BOLD}📊 COMPARISON: {expert_id}{RST}")
        print(f"    Sources: OLD={len(old_src)} HYB={len(hyb_src)} Overlap={src_overlap}")
        print(f"    Time: OLD={old_result['time_s']}s HYB={hybrid_result['time_s']}s "
              f"(+retrieval {retrieval_s}s)")

        print(f"\n  {DIM}OLD answer (300 chars): {old_result['answer'][:300]}...{RST}")
        print(f"\n  {DIM}HYB answer (300 chars): {hybrid_result['answer'][:300]}...{RST}")

        all_results.append({
            "expert_id": expert_id,
            "hybrid_mode": mode,
            "retrieval_s": retrieval_s,
            "old": {
                "input_posts": old_result["input_posts"],
                "high": old_result["high_count"],
                "medium": old_result["medium_count"],
                "enriched": old_result["enriched_count"],
                "answer": old_result["answer"],
                "main_sources": old_result["main_sources"],
                "confidence": old_result["confidence"],
                "time_s": old_result["time_s"],
                "timings": old_result["timings"],
            },
            "hybrid": {
                "input_posts": hybrid_result["input_posts"],
                "high": hybrid_result["high_count"],
                "medium": hybrid_result["medium_count"],
                "enriched": hybrid_result["enriched_count"],
                "answer": hybrid_result["answer"],
                "main_sources": hybrid_result["main_sources"],
                "confidence": hybrid_result["confidence"],
                "time_s": hybrid_result["time_s"],
                "timings": hybrid_result["timings"],
                "vector_count": hybrid_stats.get("vector_count", 0),
                "fts5_count": hybrid_stats.get("fts5_count", 0),
                "retrieval_overlap": hybrid_stats.get("overlap", 0),
            },
            "sources_overlap": src_overlap,
        })

    return {"query": query, "scout_query": scout_query, "results": all_results}


async def run_comparison(queries: list, expert_ids: list):
    """Run full comparison across all queries and experts."""
    db = SessionLocal()

    print(f"\n{BOLD}{B}{'=' * 70}{RST}")
    print(f"{BOLD}{B}  HYBRID vs OLD — Full Answer Comparison{RST}")
    print(f"{BOLD}{B}{'=' * 70}{RST}")
    print(f"  Experts: {', '.join(expert_ids)}")
    print(f"  Queries: {len(queries)}")
    print(f"  Model Map: {MODEL_MAP}")
    print(f"  Pipeline: Map → Resolve → Reduce (full)")

    all_query_results = []
    try:
        for i, query in enumerate(queries, 1):
            print(f"\n{BOLD}  [{i}/{len(queries)}]{RST}")
            result = await run_one_query(query, expert_ids, db)
            all_query_results.append(result)
    finally:
        db.close()

    # ── Summary ──
    print(f"\n{BOLD}{B}{'=' * 70}{RST}")
    print(f"{BOLD}{B}  OVERALL SUMMARY{RST}")
    print(f"{BOLD}{B}{'=' * 70}{RST}")

    print(f"\n  {'Query':<40} {'Expert':<10} {'OldSrc':>7} {'HybSrc':>7} {'Overlap':>8}")
    print(f"  {'─' * 40} {'─' * 10} {'─' * 7} {'─' * 7} {'─' * 8}")
    for qr in all_query_results:
        for r in qr["results"]:
            q_label = qr["query"][:38]
            print(
                f"  {q_label:<40} {r['expert_id']:<10} "
                f"{len(r['old']['main_sources']):>7} "
                f"{len(r['hybrid']['main_sources']):>7} "
                f"{r['sources_overlap']:>8}"
            )

    # Save JSON
    results_path = Path(__file__).parent / "deep_compare_hybrid_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "experts": expert_ids,
            "model_map": MODEL_MAP,
            "pipeline": "Map → Resolve → Reduce (full, no MediumScoring)",
            "queries": all_query_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  {G}Results saved: {results_path}{RST}")
    print(f"  {C}Open JSON to compare full answers.{RST}")
    print(f"{BOLD}{B}{'=' * 70}{RST}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Deep Compare: OLD vs HYBRID — full answer comparison"
    )
    parser.add_argument("--query", help="Single query (default: 3 preset queries)")
    parser.add_argument(
        "--experts", nargs="+", default=["doronin", "akimov"],
        help="Expert IDs (default: doronin akimov)",
    )
    args = parser.parse_args()
    queries = [args.query] if args.query else DEFAULT_QUERIES
    require_vertex_runtime()
    asyncio.run(run_comparison(queries, args.experts))


if __name__ == "__main__":
    main()
