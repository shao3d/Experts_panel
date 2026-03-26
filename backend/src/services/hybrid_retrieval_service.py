"""Hybrid Retrieval Service: Vector (sqlite-vec) + FTS5 + RRF merge.

Replaces FTS5RetrievalService for use_super_passport=True flow.
Architecture:
  1. Vector KNN via sqlite-vec (expert_id PARTITION KEY + created_at metadata pre-filter)
  2. FTS5 BM25 search (reuses sanitize_fts5_query)
  3. Soft Freshness applied to both BEFORE RRF (max penalty 0.7, linear decay)
  4. RRF merge (k=60) → ordered list of Posts for Map Phase
  5. Graceful fallback to ALL posts if no embeddings yet
"""

import json
import logging
import time
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .. import config
from ..models.post import Post
from .embedding_service import get_embedding_service
from .fts5_retrieval_service import sanitize_fts5_query

try:
    from sqlite_vec import serialize_float32
except ImportError:
    # Fallback: manual float32 serialization (should not happen in prod)
    import struct

    def serialize_float32(vector: List[float]) -> bytes:
        return struct.pack(f"{len(vector)}f", *vector)


logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """Hybrid retrieval: Vector KNN + FTS5 BM25 merged via RRF.

    Usage:
        svc = HybridRetrievalService(db)
        posts, stats = await svc.search_posts(expert_id, query, match_query)
    """

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()
        self.RRF_K = config.HYBRID_RRF_K  # 60

    async def search_posts(
        self,
        expert_id: str,
        query: str,
        match_query: str,
        cutoff_date: Optional[datetime] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> Tuple[List[Post], dict]:
        """Hybrid retrieval: Vector + FTS5 + RRF merge.

        Args:
            expert_id: Expert identifier for partition filtering
            query: Raw user query string (for vector embedding, used only if query_embedding is None)
            match_query: FTS5 MATCH query string (from AIScoutService)
            cutoff_date: Optional date filter for both vector and FTS5
            query_embedding: Pre-computed embedding vector (avoids redundant API call across experts)

        Returns:
            (posts, stats_dict) — posts in RRF-ranked order, stats for logging
        """
        vector_top_k = config.HYBRID_VECTOR_TOP_K  # 150
        fts5_top_k = config.HYBRID_FTS5_TOP_K  # 100
        t_start = time.perf_counter()

        # ══════════════════════════════════════════════
        # GRACEFUL DEGRADATION: no embeddings yet
        # (first deploy before embed_posts.py runs)
        # ══════════════════════════════════════════════
        if not self._has_embeddings(expert_id):
            logger.warning(
                f"[Hybrid] No embeddings for {expert_id}, "
                f"falling back to Standard MapReduce (all posts)"
            )
            return self._get_all_posts(expert_id, cutoff_date), {
                "mode": "fallback_no_embeddings",
                "vector_count": 0,
                "fts5_count": 0,
                "merged_count": 0,
                "final_count": 0,
                "overlap": 0,
                "vector_only": 0,
                "fts5_only": 0,
                "timings_ms": {},
            }

        # 1. Vector Search (KNN with expert_id partition key + optional date pre-filter)
        t_vec = time.perf_counter()
        if query_embedding is not None:
            embedding = query_embedding
        else:
            embedding = await self.embedding_service.embed_query(query)
        vector_results = self._vector_search(
            embedding, expert_id, cutoff_date, vector_top_k
        )
        t_vec_ms = round((time.perf_counter() - t_vec) * 1000, 1)
        # Returns: [(post_id, distance), ...] sorted by distance ASC

        # 2. FTS5 Search (reuses sanitize_fts5_query from fts5_retrieval_service)
        t_fts = time.perf_counter()
        fts5_results = self._fts5_search(
            match_query, expert_id, cutoff_date, fts5_top_k
        )
        t_fts_ms = round((time.perf_counter() - t_fts) * 1000, 1)
        # Returns: [(post_id, bm25_rank), ...] sorted by rank

        # 3. Soft Freshness Decay BEFORE RRF
        # DESIGN: Soft Freshness REPLACES HN Gravity from FTS5RetrievalService.
        # Max penalty 0.7 (linear decay over 1 year), NOT double-penalty —
        # strict decay is applied later in Map Phase.
        t_rrf = time.perf_counter()
        all_candidate_ids = list(
            set(pid for pid, _ in vector_results) | set(pid for pid, _ in fts5_results)
        )
        post_dates = self._get_post_dates(all_candidate_ids)

        # Re-score Vector: score = (1 - distance) * soft_freshness
        rescored_vector = []
        for pid, dist in vector_results:
            age_days = self._calculate_age_days(post_dates.get(pid))
            soft_freshness = max(0.7, 1.0 - (age_days / 365.0))
            sim = max(0.0, 1.0 - dist)
            rescored_vector.append((pid, sim * soft_freshness))
        rescored_vector.sort(key=lambda x: x[1], reverse=True)

        # Re-score FTS5: normalize rank → [0,1], apply soft freshness
        rescored_fts5 = []
        max_rank = max((abs(r) for _, r in fts5_results), default=1) or 1
        for pid, rank in fts5_results:
            age_days = self._calculate_age_days(post_dates.get(pid))
            soft_freshness = max(0.7, 1.0 - (age_days / 365.0))
            # FTS5 rank is negative (more negative = better match)
            norm_rank = abs(rank) / max_rank  # 0..1, higher = better
            base_score = (norm_rank * 0.7) + 0.3
            rescored_fts5.append((pid, base_score * soft_freshness))
        rescored_fts5.sort(key=lambda x: x[1], reverse=True)

        # 4. RRF Merge (rank-based, no score-scale dependencies)
        merged = self._rrf_merge(rescored_vector, rescored_fts5)
        t_rrf_ms = round((time.perf_counter() - t_rrf) * 1000, 1)

        # 5. Load Post objects preserving RRF order
        t_load = time.perf_counter()
        post_ids = [pid for pid, _ in merged]
        posts_raw = self.db.query(Post).filter(Post.post_id.in_(post_ids)).all()
        posts_by_id = {p.post_id: p for p in posts_raw}
        ordered = [posts_by_id[pid] for pid, _ in merged if pid in posts_by_id]
        t_load_ms = round((time.perf_counter() - t_load) * 1000, 1)

        t_total_ms = round((time.perf_counter() - t_start) * 1000, 1)

        vector_ids = {pid for pid, _ in vector_results}
        fts5_ids = {pid for pid, _ in fts5_results}

        stats = {
            "mode": "hybrid",
            "vector_count": len(vector_results),
            "fts5_count": len(fts5_results),
            "merged_count": len(merged),
            "final_count": len(ordered),
            "overlap": len(vector_ids & fts5_ids),
            "vector_only": len(vector_ids - fts5_ids),
            "fts5_only": len(fts5_ids - vector_ids),
            "timings_ms": {
                "vector_search": t_vec_ms,
                "fts5_search": t_fts_ms,
                "rrf_merge_freshness": t_rrf_ms,
                "post_load": t_load_ms,
                "total": t_total_ms,
            },
        }
        logger.info(
            f"[Hybrid Retrieval] {expert_id}: "
            f"vector={t_vec_ms}ms ({len(vector_results)}) | "
            f"fts5={t_fts_ms}ms ({len(fts5_results)}) | "
            f"rrf={t_rrf_ms}ms ({len(merged)}) | "
            f"load={t_load_ms}ms ({len(ordered)}) | "
            f"total={t_total_ms}ms"
        )

        return ordered, stats

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _rrf_merge(
        self,
        vector_results: List[Tuple[int, float]],
        fts5_results: List[Tuple[int, float]],
    ) -> List[Tuple[int, float]]:
        """Reciprocal Rank Fusion. Rank-based — no score normalization needed."""
        scores: dict = {}
        for rank, (post_id, _) in enumerate(vector_results, 1):
            scores[post_id] = scores.get(post_id, 0.0) + 1.0 / (self.RRF_K + rank)
        for rank, (post_id, _) in enumerate(fts5_results, 1):
            scores[post_id] = scores.get(post_id, 0.0) + 1.0 / (self.RRF_K + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _vector_search(
        self,
        embedding: List[float],
        expert_id: str,
        cutoff_date: Optional[datetime],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """KNN via sqlite-vec with expert_id PARTITION KEY pre-filter.

        cutoff_date is filtered via metadata column created_at in vec0 (pre-KNN),
        NOT via JOIN with posts (which would be post-KNN and hurt recall).
        """
        sql = """
        SELECT v.post_id, v.distance
        FROM vec_posts v
        WHERE v.expert_id = :expert_id
          AND v.embedding MATCH :embedding
          AND k = :top_k
        """
        params: dict = {
            "expert_id": expert_id,
            "embedding": serialize_float32(embedding),
            "top_k": top_k,
        }
        if cutoff_date:
            sql += " AND v.created_at >= :cutoff_date"
            params["cutoff_date"] = cutoff_date.isoformat()

        try:
            result = self.db.execute(text(sql), params)
            return [(row[0], row[1]) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"[Hybrid] Vector search failed for {expert_id}: {e}")
            return []

    def _fts5_search(
        self,
        match_query: str,
        expert_id: str,
        cutoff_date: Optional[datetime],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """FTS5 BM25 search without JOIN — uses expert_id/created_at from FTS5 directly."""
        safe_query = sanitize_fts5_query(match_query)
        if not safe_query:
            logger.warning(
                f"[Hybrid] FTS5 query rejected after sanitization: {match_query[:50]}"
            )
            return []

        sql = """
        SELECT f.rowid as post_id, f.rank as bm25_rank
        FROM posts_fts f
        WHERE posts_fts MATCH :match_query
          AND f.expert_id = :expert_id
        """
        params: dict = {"match_query": safe_query, "expert_id": expert_id}

        if cutoff_date:
            sql += " AND f.created_at >= :cutoff_date"
            params["cutoff_date"] = cutoff_date.isoformat()

        sql += " ORDER BY f.rank LIMIT :top_k"
        params["top_k"] = top_k

        try:
            result = self.db.execute(text(sql), params)
            return [(row[0], row[1]) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"[Hybrid] FTS5 search failed for {expert_id}: {e}")
            return []

    def _has_embeddings(self, expert_id: str) -> bool:
        """Check if vec_posts has any embeddings for this expert."""
        try:
            sql = "SELECT 1 FROM vec_posts WHERE expert_id = :eid LIMIT 1"
            result = self.db.execute(text(sql), {"eid": expert_id}).fetchone()
            return result is not None
        except Exception:
            return False

    def _get_all_posts(
        self, expert_id: str, cutoff_date: Optional[datetime]
    ) -> List[Post]:
        """Fallback: Standard MapReduce (all posts, as in old pipeline)."""
        query = self.db.query(Post).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30,
        )
        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)
        return query.order_by(Post.created_at.desc()).all()

    def _get_post_dates(self, post_ids: List[int]) -> dict:
        """Fetch created_at for post_ids to compute freshness scores."""
        if not post_ids:
            return {}
        rows = (
            self.db.query(Post.post_id, Post.created_at)
            .filter(Post.post_id.in_(post_ids))
            .all()
        )
        return {row[0]: row[1] for row in rows}

    def _calculate_age_days(self, created_at) -> int:
        """Calculate age of post in days for freshness decay."""
        if not created_at:
            return 365  # Default: treat as old

        if isinstance(created_at, str):
            try:
                clean_str = created_at.split(".")[0]
                created_at = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return 365

        age_days = (datetime.utcnow() - created_at).days
        return max(0, age_days)
