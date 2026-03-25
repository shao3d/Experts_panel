#!/usr/bin/env python3
"""
Deep Pipeline Comparison: OLD (MapReduce) vs NEW (FTS5 + AI Scout)

Compares what ACTUALLY enters the Reduce phase in both pipelines.
Unlike the A/B test script, this runs Map Phase directly, not through the API,
so we can see exactly which posts are classified as HIGH/MEDIUM by the LLM.

Usage (run from project root):
    python backend/scripts/deep_compare_pipelines.py --query "Как работать со Skills?"
    python backend/scripts/deep_compare_pipelines.py --query "..." --experts doronin akimov

Requirements:
    - .env file in backend/ with GOOGLE_AI_STUDIO_API_KEY
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

# ─── Path setup ───
BACKEND_DIR = Path(__file__).parent.parent
ENV_PATH = BACKEND_DIR / ".env"
DB_PATH = BACKEND_DIR / "data" / "experts.db"

from dotenv import load_dotenv
load_dotenv(ENV_PATH)

import os
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func
from src.models.base import SessionLocal
from src.models.post import Post
from src.services.map_service import MapService
from src.services.fts5_retrieval_service import FTS5RetrievalService
from src.services.ai_scout_service import AIScoutService
from src.config import MODEL_MAP, MAP_CHUNK_SIZE, MAP_MAX_PARALLEL, MAX_FTS_RESULTS

# ─── Logging ───
logging.basicConfig(
    level=logging.WARNING,  # Suppress noisy service logs
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ANSI colors
G = '\033[92m'  # Green
Y = '\033[93m'  # Yellow
R = '\033[91m'  # Red
B = '\033[94m'  # Blue
C = '\033[96m'  # Cyan
BOLD = '\033[1m'
DIM = '\033[2m'
RST = '\033[0m'


def get_all_posts(db, expert_id: str, max_posts: int = None):
    """Get all text posts for an expert (OLD pipeline behavior)."""
    query = db.query(Post).filter(
        Post.expert_id == expert_id,
        Post.message_text.isnot(None),
        func.length(Post.message_text) > 30
    ).order_by(Post.created_at.desc())
    if max_posts:
        query = query.limit(max_posts)
    return query.all()


def extract_map_results(map_result: dict):
    """Extract HIGH and MEDIUM post IDs from Map Phase result."""
    relevant = map_result.get("relevant_posts", [])
    high = {p["telegram_message_id"] for p in relevant if p.get("relevance") == "HIGH"}
    medium = {p["telegram_message_id"] for p in relevant if p.get("relevance") == "MEDIUM"}
    all_relevant = high | medium
    
    # Build detail dict for later analysis
    details = {}
    for p in relevant:
        if p.get("relevance") in ("HIGH", "MEDIUM"):
            details[p["telegram_message_id"]] = {
                "relevance": p.get("relevance"),
                "reason": p.get("reason", ""),
            }
    
    return high, medium, all_relevant, details


async def run_comparison(query: str, expert_ids: list):
    """Run deep comparison for a query across given experts."""
    db = SessionLocal()
    
    print(f"\n{BOLD}{B}{'='*70}{RST}")
    print(f"{BOLD}{B}  Deep Pipeline Comparison{RST}")
    print(f"{BOLD}{B}{'='*70}{RST}")
    print(f"  Query: {C}{query}{RST}")
    print(f"  Experts: {', '.join(expert_ids)}")
    print(f"  Model: {MODEL_MAP}")
    print(f"  FTS5 limit: {MAX_FTS_RESULTS}")
    print()

    # 1. Generate Scout query (shared across experts)
    print(f"{Y}⏳ AI Scout generating FTS5 query...{RST}")
    scout = AIScoutService()
    scout_query, scout_success = await scout.generate_match_query(query)
    print(f"  Scout query: {C}{scout_query[:100]}...{RST}")
    print(f"  Scout success: {'✅' if scout_success else '⚠️ fallback'}")
    print()

    all_results = []

    for expert_id in expert_ids:
        print(f"{BOLD}{C}{'─'*70}{RST}")
        print(f"{BOLD}{C}  Expert: {expert_id}{RST}")
        print(f"{C}{'─'*70}{RST}")

        # ── OLD Pipeline: ALL posts → Map ──
        print(f"\n  {Y}▶ OLD Pipeline (ALL posts → Map)...{RST}")
        all_posts = get_all_posts(db, expert_id)
        print(f"    Posts loaded: {len(all_posts)}")

        map_service_old = MapService(
            model=MODEL_MAP,
            chunk_size=MAP_CHUNK_SIZE,
            max_parallel=MAP_MAX_PARALLEL
        )

        t0 = time.time()
        old_map_result = await map_service_old.process(
            posts=all_posts,
            query=query,
            expert_id=expert_id
        )
        old_time = time.time() - t0

        old_high, old_medium, old_relevant, old_details = extract_map_results(old_map_result)
        old_stats = old_map_result.get("statistics", {})

        print(f"    ⏱  Time: {old_time:.1f}s")
        print(f"    📊 HIGH: {len(old_high)}, MEDIUM: {len(old_medium)}, "
              f"LOW: {old_stats.get('low_relevance', '?')}")
        print(f"    Errors: {len(old_map_result.get('chunks_with_errors', []))}")

        # ── NEW Pipeline: FTS5 → Map ──
        print(f"\n  {Y}▶ NEW Pipeline (FTS5 + Scout → Map)...{RST}")

        fts5_service = FTS5RetrievalService(db)
        fts5_posts, used_fts5 = fts5_service.search_posts(
            expert_id=expert_id,
            match_query=scout_query,
            exclude_media_only=True,
            use_hybrid=True  # Will be 0 random thanks to the fix
        )
        print(f"    FTS5 posts: {len(fts5_posts)} (used_fts5: {used_fts5})")

        map_service_new = MapService(
            model=MODEL_MAP,
            chunk_size=MAP_CHUNK_SIZE,
            max_parallel=MAP_MAX_PARALLEL
        )

        t0 = time.time()
        new_map_result = await map_service_new.process(
            posts=fts5_posts,
            query=query,
            expert_id=expert_id
        )
        new_time = time.time() - t0

        new_high, new_medium, new_relevant, new_details = extract_map_results(new_map_result)
        new_stats = new_map_result.get("statistics", {})

        print(f"    ⏱  Time: {new_time:.1f}s")
        print(f"    📊 HIGH: {len(new_high)}, MEDIUM: {len(new_medium)}, "
              f"LOW: {new_stats.get('low_relevance', '?')}")
        print(f"    Errors: {len(new_map_result.get('chunks_with_errors', []))}")

        # ── Comparison ──
        print(f"\n  {BOLD}📊 COMPARISON: {expert_id}{RST}")

        # Posts that OLD found relevant but NEW didn't even have in FTS5
        fts5_post_ids = {p.post_id for p in fts5_posts}
        old_relevant_not_in_fts5 = {pid for pid in old_relevant if pid not in fts5_post_ids}
        
        # Posts OLD found relevant, NEW had in FTS5 but Map didn't pick them
        old_relevant_in_fts5_but_new_missed = (old_relevant & fts5_post_ids) - new_relevant
        
        # Posts NEW found relevant that OLD missed (NEW wins)
        new_only = new_relevant - old_relevant

        # True recall: of OLD's relevant, how many did NEW also find relevant?
        true_recall = len(old_relevant & new_relevant) / len(old_relevant) if old_relevant else 1.0

        print(f"    OLD relevant (H+M): {len(old_relevant)}")
        print(f"    NEW relevant (H+M): {len(new_relevant)}")
        print(f"    Overlap:            {len(old_relevant & new_relevant)}")
        
        recall_color = G if true_recall >= 0.8 else (Y if true_recall >= 0.6 else R)
        print(f"    {BOLD}True Recall: {recall_color}{true_recall:.1%}{RST}")
        
        print(f"\n    Loss breakdown:")
        print(f"      FTS5 didn't find:      {R}{len(old_relevant_not_in_fts5)}{RST} posts")
        print(f"      In FTS5 but Map missed: {Y}{len(old_relevant_in_fts5_but_new_missed)}{RST} posts")
        print(f"      NEW found, OLD missed:  {G}{len(new_only)}{RST} posts")

        latency_improvement = (old_time - new_time) / old_time * 100 if old_time > 0 else 0
        lat_color = G if latency_improvement > 0 else R
        print(f"\n    ⏱  Latency: {old_time:.1f}s → {new_time:.1f}s "
              f"({lat_color}{latency_improvement:+.0f}%{RST})")

        # ── Show lost posts ──
        if old_relevant_not_in_fts5:
            print(f"\n  {R}🔍 Posts LOST by FTS5 (not in index results):{RST}")
            posts_by_id = {p.post_id: p for p in all_posts}
            shown = 0
            for pid in sorted(old_relevant_not_in_fts5):
                if pid in posts_by_id and shown < 10:
                    post = posts_by_id[pid]
                    rel = old_details.get(pid, {}).get("relevance", "?")
                    reason = old_details.get(pid, {}).get("reason", "")[:80]
                    text_preview = (post.message_text or "")[:80].replace('\n', ' ')
                    print(f"    {DIM}[{rel}]{RST} msg_id={pid}: {text_preview}...")
                    if reason:
                        print(f"         {DIM}reason: {reason}{RST}")
                    shown += 1
            if len(old_relevant_not_in_fts5) > 10:
                print(f"    ... and {len(old_relevant_not_in_fts5) - 10} more")

        all_results.append({
            "expert_id": expert_id,
            "old_input": len(all_posts),
            "new_input": len(fts5_posts),
            "old_relevant": len(old_relevant),
            "new_relevant": len(new_relevant),
            "overlap": len(old_relevant & new_relevant),
            "true_recall": round(true_recall, 3),
            "lost_by_fts5": len(old_relevant_not_in_fts5),
            "lost_by_map": len(old_relevant_in_fts5_but_new_missed),
            "new_only_wins": len(new_only),
            "old_time_s": round(old_time, 1),
            "new_time_s": round(new_time, 1),
        })

    # ── Final Summary ──
    print(f"\n{BOLD}{B}{'='*70}{RST}")
    print(f"{BOLD}{B}  SUMMARY{RST}")
    print(f"{BOLD}{B}{'='*70}{RST}")

    total_old_relevant = sum(r["old_relevant"] for r in all_results)
    total_overlap = sum(r["overlap"] for r in all_results)
    total_recall = total_overlap / total_old_relevant if total_old_relevant else 1.0
    total_lost_fts5 = sum(r["lost_by_fts5"] for r in all_results)
    total_lost_map = sum(r["lost_by_map"] for r in all_results)
    total_new_wins = sum(r["new_only_wins"] for r in all_results)

    recall_color = G if total_recall >= 0.8 else (Y if total_recall >= 0.6 else R)
    print(f"  {BOLD}Overall True Recall: {recall_color}{total_recall:.1%}{RST}")
    print(f"  Lost by FTS5:  {total_lost_fts5}")
    print(f"  Lost by Map:   {total_lost_map}")
    print(f"  NEW-only wins: {total_new_wins}")

    # Save results
    results_path = Path(__file__).parent / "deep_compare_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "query": query,
            "scout_query": scout_query,
            "experts": expert_ids,
            "timestamp": datetime.utcnow().isoformat(),
            "model": MODEL_MAP,
            "total_recall": round(total_recall, 3),
            "results": all_results
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  {G}Results saved to: {results_path}{RST}")

    db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Deep Pipeline Comparison: OLD vs NEW")
    parser.add_argument("--query", required=True, help="Query to test")
    parser.add_argument("--experts", nargs="+", default=["doronin", "akimov"],
                        help="Expert IDs (default: doronin akimov)")
    args = parser.parse_args()

    asyncio.run(run_comparison(args.query, args.experts))


if __name__ == "__main__":
    main()
