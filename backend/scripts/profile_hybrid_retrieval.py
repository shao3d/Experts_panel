"""
Profiling script for Hybrid Retrieval pipeline.

Measures each stage individually with wall-clock timing:
  1. sqlite-vec availability check
  2. _has_embeddings() check
  3. Embedding API call latency (single + repeated)
  4. Vector KNN search latency
  5. FTS5 BM25 search latency
  6. _get_post_dates latency
  7. RRF merge + freshness scoring latency
  8. Post loading (ORM) latency
  9. Full search_posts() end-to-end
  10. Concurrent search_posts() simulation (5 experts)

Usage:
    cd backend && python -m scripts.profile_hybrid_retrieval
"""

import asyncio
import json
import sys
import time
import struct
import warnings
from datetime import datetime
from pathlib import Path

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
    logger_name="cli.profile_hybrid_retrieval",
)
DB_PATH = set_default_sqlite_database_url(BACKEND_DIR, force=True)

from src.models.base import SessionLocal, engine
from src.models.post import Post
from src import config
from sqlalchemy import text


def timed(label):
    """Simple context manager for timing."""

    class Timer:
        def __init__(self):
            self.elapsed_ms = 0

        def __enter__(self):
            self.start = time.perf_counter()
            return self

        def __exit__(self, *args):
            self.elapsed_ms = round((time.perf_counter() - self.start) * 1000, 2)

    return Timer()


async def main():
    require_vertex_runtime()
    results = {}

    print("=" * 70)
    print("  HYBRID RETRIEVAL PROFILING DIAGNOSTIC")
    print(f"  Time: {datetime.now().isoformat()}")
    print(f"  DB: {config.DATABASE_URL}")
    print("=" * 70)

    # ─────────────────────────────────────────────
    # TEST 0: Check sqlite-vec availability
    # ─────────────────────────────────────────────
    print("\n🔧 TEST 0: sqlite-vec availability")
    db = SessionLocal()
    sqlite_vec_available = False
    try:
        row = db.execute(text("SELECT vec_version()")).fetchone()
        sqlite_vec_available = True
        print(f"   ✅ sqlite-vec loaded: version {row[0]}")
    except Exception as e:
        print(f"   ❌ sqlite-vec NOT available: {e}")
        print("   ⚠️  Hybrid retrieval will FALLBACK to all posts!")
    results["sqlite_vec_available"] = sqlite_vec_available

    # Check if vec_posts table exists and has data
    if sqlite_vec_available:
        try:
            count = db.execute(text("SELECT COUNT(*) FROM vec_posts")).fetchone()[0]
            print(f"   📊 vec_posts rows: {count}")
            results["vec_posts_count"] = count

            experts_rows = db.execute(
                text(
                    "SELECT expert_id, COUNT(*) as cnt FROM vec_posts GROUP BY expert_id"
                )
            ).fetchall()
            experts_info = {row[0]: row[1] for row in experts_rows}
            print(f"   📊 Experts with embeddings: {json.dumps(experts_info)}")
            results["experts_embedding_counts"] = experts_info
        except Exception as e:
            print(f"   ⚠️  vec_posts query failed: {e}")
            results["vec_posts_count"] = 0
            experts_info = {}
    else:
        experts_info = {}

    # Check total posts
    total_posts = db.execute(text("SELECT COUNT(*) FROM posts")).fetchone()[0]
    print(f"   📊 Total posts: {total_posts}")

    # Get available expert IDs
    expert_rows = db.execute(
        text("SELECT DISTINCT expert_id FROM posts WHERE expert_id IS NOT NULL")
    ).fetchall()
    expert_ids = [r[0] for r in expert_rows]
    print(f"   📊 Expert IDs: {expert_ids}")
    results["total_posts"] = total_posts
    results["expert_ids"] = expert_ids
    db.close()

    if not expert_ids:
        print("\n❌ No experts found. Cannot continue.")
        return

    # Choose a test expert (prefer one with embeddings)
    test_expert = expert_ids[0]
    if experts_info:
        # Pick expert with most embeddings
        test_expert = max(experts_info, key=experts_info.get)
    print(f"\n   🎯 Test expert: {test_expert}")

    test_query = "Как работать со Skills в AI агентах?"
    test_match_query = (
        "agent* OR агент* OR ai OR ии OR skill* OR навык* OR tool* OR инструмент*"
    )

    # ─────────────────────────────────────────────
    # TEST 1: _has_embeddings() latency
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 1: _has_embeddings() latency")
    db = SessionLocal()
    timings_has_emb = []
    for i in range(5):
        with timed("has_emb") as t:
            try:
                sql = "SELECT 1 FROM vec_posts WHERE expert_id = :eid LIMIT 1"
                row = db.execute(text(sql), {"eid": test_expert}).fetchone()
            except:
                pass
        timings_has_emb.append(t.elapsed_ms)
    db.close()
    avg_has_emb = round(sum(timings_has_emb) / len(timings_has_emb), 2)
    print(f"   Runs: {timings_has_emb} ms")
    print(f"   Avg: {avg_has_emb} ms")
    results["has_embeddings_ms"] = {"runs": timings_has_emb, "avg": avg_has_emb}

    # ─────────────────────────────────────────────
    # TEST 2: Embedding API latency
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 2: Embedding API latency (embed_query)")
    from src.services.embedding_service import get_embedding_service

    emb_service = get_embedding_service()

    embed_timings = []
    query_embedding = None
    for i in range(3):
        with timed("embed") as t:
            query_embedding = await emb_service.embed_query(test_query)
        embed_timings.append(t.elapsed_ms)
        print(f"   Call {i + 1}: {t.elapsed_ms} ms (dim={len(query_embedding)})")

    avg_embed = round(sum(embed_timings) / len(embed_timings), 2)
    print(f"   Avg: {avg_embed} ms")
    results["embed_query_ms"] = {"runs": embed_timings, "avg": avg_embed}

    # ─────────────────────────────────────────────
    # TEST 3: Vector KNN search latency
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 3: Vector KNN search latency (_vector_search)")

    if not sqlite_vec_available or not query_embedding:
        print("   ⏭️  SKIPPED (sqlite-vec not available or no embedding)")
        results["vector_search_ms"] = "SKIPPED"
    else:
        try:
            from sqlite_vec import serialize_float32
        except ImportError:

            def serialize_float32(v):
                return struct.pack(f"{len(v)}f", *v)

        db = SessionLocal()
        vector_timings = []
        vector_count = 0
        for i in range(5):
            with timed("vec") as t:
                sql = """
                SELECT v.post_id, v.distance
                FROM vec_posts v
                WHERE v.expert_id = :expert_id
                  AND v.embedding MATCH :embedding
                  AND k = :top_k
                """
                rows = db.execute(
                    text(sql),
                    {
                        "expert_id": test_expert,
                        "embedding": serialize_float32(query_embedding),
                        "top_k": config.HYBRID_VECTOR_TOP_K,
                    },
                ).fetchall()
                vector_count = len(rows)
            vector_timings.append(t.elapsed_ms)
        db.close()

        avg_vec = round(sum(vector_timings) / len(vector_timings), 2)
        print(f"   Results: {vector_count} posts")
        print(f"   Runs: {vector_timings} ms")
        print(f"   Avg: {avg_vec} ms")
        results["vector_search_ms"] = {
            "runs": vector_timings,
            "avg": avg_vec,
            "results": vector_count,
        }

    # ─────────────────────────────────────────────
    # TEST 4: FTS5 BM25 search latency
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 4: FTS5 BM25 search latency (_fts5_search)")
    db = SessionLocal()
    fts5_timings = []
    fts5_count = 0

    from src.services.fts5_retrieval_service import sanitize_fts5_query

    safe_query = sanitize_fts5_query(test_match_query)

    for i in range(5):
        with timed("fts5") as t:
            sql = """
            SELECT f.rowid as post_id, f.rank as bm25_rank
            FROM posts_fts f
            WHERE posts_fts MATCH :match_query
              AND f.expert_id = :expert_id
            ORDER BY f.rank LIMIT :top_k
            """
            rows = db.execute(
                text(sql),
                {
                    "match_query": safe_query,
                    "expert_id": test_expert,
                    "top_k": config.HYBRID_FTS5_TOP_K,
                },
            ).fetchall()
            fts5_count = len(rows)
        fts5_timings.append(t.elapsed_ms)
    db.close()

    avg_fts5 = round(sum(fts5_timings) / len(fts5_timings), 2)
    print(f"   Results: {fts5_count} posts")
    print(f"   Runs: {fts5_timings} ms")
    print(f"   Avg: {avg_fts5} ms")
    results["fts5_search_ms"] = {
        "runs": fts5_timings,
        "avg": avg_fts5,
        "results": fts5_count,
    }

    # ─────────────────────────────────────────────
    # TEST 5: _get_post_dates latency
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 5: _get_post_dates latency (freshness data)")
    db = SessionLocal()
    # Collect post_ids from vector + fts5 results
    sample_post_ids = [
        row[0]
        for row in db.execute(
            text("SELECT post_id FROM posts WHERE expert_id = :eid LIMIT 200"),
            {"eid": test_expert},
        ).fetchall()
    ]

    dates_timings = []
    for i in range(5):
        with timed("dates") as t:
            if sample_post_ids:
                placeholders = ",".join([str(pid) for pid in sample_post_ids])
                rows = db.execute(
                    text(
                        f"SELECT post_id, created_at FROM posts WHERE post_id IN ({placeholders})"
                    )
                ).fetchall()
        dates_timings.append(t.elapsed_ms)
    db.close()

    avg_dates = round(sum(dates_timings) / len(dates_timings), 2)
    print(f"   Post IDs: {len(sample_post_ids)}")
    print(f"   Runs: {dates_timings} ms")
    print(f"   Avg: {avg_dates} ms")
    results["get_post_dates_ms"] = {"runs": dates_timings, "avg": avg_dates}

    # ─────────────────────────────────────────────
    # TEST 6: Post loading (ORM) latency
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 6: Post loading (ORM) latency")
    db = SessionLocal()
    load_timings = []
    load_count = 0
    for i in range(3):
        with timed("load") as t:
            posts = db.query(Post).filter(Post.post_id.in_(sample_post_ids[:200])).all()
            load_count = len(posts)
        load_timings.append(t.elapsed_ms)
    db.close()

    avg_load = round(sum(load_timings) / len(load_timings), 2)
    print(f"   Posts loaded: {load_count}")
    print(f"   Runs: {load_timings} ms")
    print(f"   Avg: {avg_load} ms")
    results["post_load_orm_ms"] = {
        "runs": load_timings,
        "avg": avg_load,
        "count": load_count,
    }

    # ─────────────────────────────────────────────
    # TEST 7: FULL search_posts() — single expert
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 7: FULL search_posts() — single expert, end-to-end")
    from src.services.hybrid_retrieval_service import HybridRetrievalService

    full_timings = []
    for i in range(3):
        db = SessionLocal()
        svc = HybridRetrievalService(db)
        with timed("full") as t:
            posts, stats = await svc.search_posts(
                expert_id=test_expert,
                query=test_query,
                match_query=test_match_query,
            )
        full_timings.append(t.elapsed_ms)
        print(
            f"   Run {i + 1}: {t.elapsed_ms} ms → {len(posts)} posts, stats={json.dumps(stats)}"
        )
        db.close()

    avg_full = round(sum(full_timings) / len(full_timings), 2)
    print(f"   Avg: {avg_full} ms")
    results["full_search_posts_ms"] = {"runs": full_timings, "avg": avg_full}

    # ─────────────────────────────────────────────
    # TEST 8: CONCURRENT search_posts() — 5 experts or same expert ×5
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 8: CONCURRENT search_posts() — simulating 5 parallel experts")

    concurrent_experts = expert_ids[:5] if len(expert_ids) >= 5 else expert_ids * 5
    concurrent_experts = concurrent_experts[:5]

    # 8a: Sequential (baseline)
    seq_timings = []
    with timed("sequential") as t_seq:
        for eid in concurrent_experts:
            db = SessionLocal()
            svc = HybridRetrievalService(db)
            t0 = time.perf_counter()
            posts, stats = await svc.search_posts(
                expert_id=eid,
                query=test_query,
                match_query=test_match_query,
            )
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            seq_timings.append(elapsed)
            db.close()
    total_seq = t_seq.elapsed_ms
    print(f"   Sequential: {seq_timings} ms each")
    print(f"   Sequential total: {total_seq} ms")

    # 8b: Concurrent with SHARED session (like production!)
    print("\n   Testing concurrent with SHARED db session...")
    db_shared = SessionLocal()
    with timed("concurrent_shared") as t_conc_shared:

        async def run_one_shared(eid):
            svc = HybridRetrievalService(db_shared)
            t0 = time.perf_counter()
            posts, stats = await svc.search_posts(
                expert_id=eid, query=test_query, match_query=test_match_query
            )
            return round((time.perf_counter() - t0) * 1000, 2), eid

        conc_results_shared = await asyncio.gather(
            *[run_one_shared(eid) for eid in concurrent_experts], return_exceptions=True
        )
    db_shared.close()
    total_conc_shared = t_conc_shared.elapsed_ms

    conc_shared_timings = []
    for r in conc_results_shared:
        if isinstance(r, Exception):
            print(f"   ❌ Error: {r}")
            conc_shared_timings.append(f"ERROR: {r}")
        else:
            conc_shared_timings.append(r[0])
            print(f"   Expert {r[1]}: {r[0]} ms")
    print(f"   Concurrent (shared session) total: {total_conc_shared} ms")

    # 8c: Concurrent with SEPARATE sessions
    print("\n   Testing concurrent with SEPARATE db sessions...")
    with timed("concurrent_separate") as t_conc_sep:

        async def run_one_separate(eid):
            db_local = SessionLocal()
            svc = HybridRetrievalService(db_local)
            t0 = time.perf_counter()
            try:
                posts, stats = await svc.search_posts(
                    expert_id=eid, query=test_query, match_query=test_match_query
                )
                return round((time.perf_counter() - t0) * 1000, 2), eid
            finally:
                db_local.close()

        conc_results_sep = await asyncio.gather(
            *[run_one_separate(eid) for eid in concurrent_experts],
            return_exceptions=True,
        )
    total_conc_sep = t_conc_sep.elapsed_ms

    conc_sep_timings = []
    for r in conc_results_sep:
        if isinstance(r, Exception):
            print(f"   ❌ Error: {r}")
            conc_sep_timings.append(f"ERROR: {r}")
        else:
            conc_sep_timings.append(r[0])
            print(f"   Expert {r[1]}: {r[0]} ms")
    print(f"   Concurrent (separate sessions) total: {total_conc_sep} ms")

    # 8d: Concurrent with PRE-CACHED embedding
    print("\n   Testing concurrent with PRE-CACHED embedding...")
    cached_embedding = await emb_service.embed_query(test_query)  # warm up

    with timed("concurrent_cached") as t_conc_cached:

        async def run_one_cached(eid):
            db_local = SessionLocal()
            svc = HybridRetrievalService(db_local)
            t0 = time.perf_counter()
            try:
                # Bypass embed_query by calling internals directly
                if svc._has_embeddings(eid):
                    from sqlite_vec import serialize_float32 as sf32

                    vector_results = svc._vector_search(
                        cached_embedding, eid, None, config.HYBRID_VECTOR_TOP_K
                    )
                    fts5_results = svc._fts5_search(
                        test_match_query, eid, None, config.HYBRID_FTS5_TOP_K
                    )
                    all_ids = list(
                        set(p for p, _ in vector_results)
                        | set(p for p, _ in fts5_results)
                    )
                    post_dates = svc._get_post_dates(all_ids)
                    count = len(vector_results) + len(fts5_results)
                else:
                    count = 0
                return round((time.perf_counter() - t0) * 1000, 2), eid, count
            finally:
                db_local.close()

        conc_results_cached = await asyncio.gather(
            *[run_one_cached(eid) for eid in concurrent_experts], return_exceptions=True
        )
    total_conc_cached = t_conc_cached.elapsed_ms

    for r in conc_results_cached:
        if isinstance(r, Exception):
            print(f"   ❌ Error: {r}")
        else:
            print(f"   Expert {r[1]}: {r[0]} ms ({r[2]} results)")
    print(f"   Concurrent (cached embedding) total: {total_conc_cached} ms")

    results["concurrent_tests"] = {
        "sequential_ms": {"per_expert": seq_timings, "total": total_seq},
        "concurrent_shared_session_ms": {
            "per_expert": conc_shared_timings,
            "total": total_conc_shared,
        },
        "concurrent_separate_sessions_ms": {
            "per_expert": conc_sep_timings,
            "total": total_conc_sep,
        },
        "concurrent_cached_embedding_ms": {"total": total_conc_cached},
    }

    # ─────────────────────────────────────────────
    # TEST 9: Event loop blocking test
    # ─────────────────────────────────────────────
    print("\n⏱️  TEST 9: Event loop blocking test")
    print("   Measuring how long sync SQL blocks the event loop...")

    db = SessionLocal()

    # Schedule a canary coroutine and see when it gets to run
    canary_delays = []

    async def canary():
        """Measures event loop availability."""
        start = time.perf_counter()
        await asyncio.sleep(0)  # Yield to event loop
        return time.perf_counter() - start

    # Run 5 sync SQL operations back-to-back and measure canary delay
    for i in range(3):
        # Start canary, then block event loop with sync SQL
        canary_task = asyncio.create_task(canary())

        # Sync blocking operations (simulates _vector_search + _fts5_search + _get_post_dates + post load)
        t0 = time.perf_counter()
        try:
            if sqlite_vec_available:
                db.execute(
                    text("""
                    SELECT v.post_id, v.distance FROM vec_posts v
                    WHERE v.expert_id = :eid AND v.embedding MATCH :emb AND k = :k
                """),
                    {
                        "eid": test_expert,
                        "embedding": serialize_float32(query_embedding),
                        "k": 150,
                    },
                ).fetchall()
        except:
            pass
        db.execute(
            text("""
            SELECT f.rowid, f.rank FROM posts_fts f
            WHERE posts_fts MATCH :q AND f.expert_id = :eid
            ORDER BY f.rank LIMIT 100
        """),
            {"q": safe_query, "eid": test_expert},
        ).fetchall()

        db.query(Post).filter(Post.expert_id == test_expert).limit(200).all()

        block_time = round((time.perf_counter() - t0) * 1000, 2)

        canary_delay = round((await canary_task) * 1000, 2)
        canary_delays.append(canary_delay)
        print(
            f"   Run {i + 1}: sync SQL took {block_time} ms, canary delay: {canary_delay} ms"
        )

    db.close()
    avg_canary = round(sum(canary_delays) / len(canary_delays), 2)
    print(f"   Avg canary delay (= event loop block time): {avg_canary} ms")
    results["event_loop_block_ms"] = {"canary_delays": canary_delays, "avg": avg_canary}

    # ─────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"""
  sqlite-vec available:     {sqlite_vec_available}
  Embedding API (avg):      {results.get("embed_query_ms", {}).get("avg", "N/A")} ms
  Vector KNN search (avg):  {results.get("vector_search_ms", {}).get("avg", "N/A") if isinstance(results.get("vector_search_ms"), dict) else results.get("vector_search_ms", "N/A")} ms
  FTS5 BM25 search (avg):   {results.get("fts5_search_ms", {}).get("avg", "N/A")} ms
  Post dates query (avg):   {results.get("get_post_dates_ms", {}).get("avg", "N/A")} ms
  Post ORM loading (avg):   {results.get("post_load_orm_ms", {}).get("avg", "N/A")} ms
  Full search_posts (avg):  {results.get("full_search_posts_ms", {}).get("avg", "N/A")} ms
  Event loop block (avg):   {avg_canary} ms
  
  CONCURRENT (5 experts):
    Sequential total:           {results.get("concurrent_tests", {}).get("sequential_ms", {}).get("total", "N/A")} ms
    Concurrent (shared sess):   {results.get("concurrent_tests", {}).get("concurrent_shared_session_ms", {}).get("total", "N/A")} ms
    Concurrent (separate sess): {results.get("concurrent_tests", {}).get("concurrent_separate_sessions_ms", {}).get("total", "N/A")} ms
    Concurrent (cached embed):  {results.get("concurrent_tests", {}).get("concurrent_cached_embedding_ms", {}).get("total", "N/A")} ms
    """)

    # Save full results
    output_path = os.path.join(os.path.dirname(__file__), "profile_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  📝 Full results saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
