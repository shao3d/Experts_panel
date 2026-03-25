"""FTS5 Retrieval Service for Super-Passport Search.

Provides full-text search capabilities using SQLite FTS5 for pre-filtering
posts before the Map Phase, reducing token usage and latency.
"""

import json
import logging
import random
import re
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from ..models.post import Post
from ..config import MAX_FTS_RESULTS

logger = logging.getLogger(__name__)


def sanitize_fts5_query(query: str) -> str:
    """Sanitize FTS5 MATCH query to prevent injection and syntax errors.

    FTS5 has special characters that need careful handling:
    - Parentheses must be balanced
    - Quotes must be balanced
    - Special chars: * ^ ( ) " ' -
    - Column names cannot be injected

    Args:
        query: Raw FTS5 query string

    Returns:
        Sanitized query safe for FTS5 MATCH clause
    """
    if not query or not query.strip():
        return ""

    original = query

    # Remove any attempt to reference column names (FTS5 injection)
    # FTS5 syntax: column:term - we only allow searching all columns
    query = re.sub(r'\b\w+\s*:', '', query)

    # Remove dangerous SQL characters that could escape the MATCH context
    # NOTE: Double quotes (") are NOT removed to allow FTS5 phrase search (e.g., "си плюс плюс")
    # Only remove: ; ' \
    query = re.sub(r'[;\'\\]', '', query)

    # Check parentheses balance
    if query.count('(') != query.count(')'):
        logger.warning(f"[FTS5 Sanitize] Unbalanced parentheses, simplifying: {original[:50]}")
        # Remove all parentheses as a safe fallback
        query = re.sub(r'[()]', '', query)

    # Check quotes balance
    if query.count('"') % 2 != 0:
        logger.warning(f"[FTS5 Sanitize] Unbalanced quotes, removing: {original[:50]}")
        query = query.replace('"', '')

    # Limit query length to prevent DoS
    if len(query) > 500:
        logger.warning(f"[FTS5 Sanitize] Query too long ({len(query)}), truncating")
        query = query[:500]

    # Validate that query still has meaningful content
    cleaned = query.strip()
    if not cleaned or len(cleaned) < 2:
        logger.warning(f"[FTS5 Sanitize] Query empty after sanitization: {original[:50]}")
        return ""

    return cleaned


class FTS5RetrievalService:
    """Service for retrieving posts using FTS5 full-text search.

    Pre-filters posts using SQLite FTS5 index before Map Phase.
    Falls back to standard retrieval if FTS5 returns no results.

    Entity-Centric v2:
    - Smart Fallback triggers when FTS5 < MIN_FTS5_RESULTS
    - Hybrid Mode: FTS5 + Random Sample for better recall
    """

    # Minimum FTS5 results before triggering Smart Fallback
    MIN_FTS5_RESULTS = 10
    # Hybrid mode: percentage of posts to add as random sample
    # DISABLED (0.0) — metadata enrichment provides semantic coverage now
    HYBRID_SAMPLE_RATIO = 0.0
    # Hybrid mode: minimum random sample size
    # NOTE: Must be 0 when RATIO is 0.0, otherwise max(MIN, 0) still dosypates!
    HYBRID_MIN_SAMPLE = 0

    def __init__(self, db: Session, max_results: int = None):
        """Initialize FTS5 retrieval service.

        Args:
            db: Database session
            max_results: Maximum posts to retrieve (default: MAX_FTS_RESULTS from config)
        """
        self.db = db
        self.max_results = max_results or MAX_FTS_RESULTS

    def search_posts(
        self,
        expert_id: str,
        match_query: str,
        cutoff_date: Optional[datetime] = None,
        exclude_media_only: bool = True,
        use_hybrid: bool = True
    ) -> Tuple[List[Post], bool]:
        """Search posts using FTS5 MATCH query.

        Entity-Centric v2:
        - Smart Fallback if FTS5 returns < MIN_FTS5_RESULTS
        - Hybrid Mode: FTS5 + Random Sample for better recall

        Args:
            expert_id: Expert identifier
            match_query: FTS5 MATCH query string (e.g., "kubernetes OR кубер*")
            cutoff_date: Optional date filter (only posts >= this date)
            exclude_media_only: Exclude posts with <= 30 characters
            use_hybrid: Enable hybrid mode (FTS5 + random sample)

        Returns:
            Tuple of (posts list, used_fts5 flag)
            used_fts5 is True if FTS5 returned sufficient results, False if fallback was used
        """
        try:
            # CRITICAL: Sanitize FTS5 query to prevent injection
            safe_query = sanitize_fts5_query(match_query)
            if not safe_query:
                logger.warning(f"[FTS5] Query rejected after sanitization: {match_query[:50]}...")
                return [], False

            # Build FTS5 query
            sql = self._build_fts5_query(expert_id, safe_query, cutoff_date, exclude_media_only)

            result = self.db.execute(text(sql), {
                "expert_id": expert_id,
                "match_query": safe_query,
                "cutoff_date": cutoff_date.isoformat() if cutoff_date else None,
                "max_results": self.max_results
            })

            # Fetch (post_id, bm25_rank, created_at)
            # In SQLite FTS5, rank is a negative number where more negative = better match
            raw_results = result.fetchall()
            fts5_post_ids = set(row[0] for row in raw_results)

            # ═══════════════════════════════════════════════════════════════
            # SMART FALLBACK (Entity-Centric v2)
            # If FTS5 returns too few results, fall back to ALL posts
            # ═══════════════════════════════════════════════════════════════
            if len(fts5_post_ids) < self.MIN_FTS5_RESULTS:
                logger.warning(f"[FTS5 Smart Fallback] Low results ({len(fts5_post_ids)} < {self.MIN_FTS5_RESULTS}), "
                               f"falling back to ALL posts for expert {expert_id}")

                fallback_posts = self.get_fallback_posts(
                    expert_id=expert_id,
                    cutoff_date=cutoff_date,
                    max_posts=self.max_results
                )

                logger.info(f"[FTS5 Metrics] " + json.dumps({
                    "event": "smart_fallback",
                    "expert_id": expert_id,
                    "fts5_results": len(fts5_post_ids),
                    "fallback_results": len(fallback_posts),
                    "query": match_query[:50]
                }, ensure_ascii=False))

                return fallback_posts, False

            # ═══════════════════════════════════════════════════════════════
            # HYBRID MODE (Entity-Centric v2)
            # Add random sample to cover "semantic gap"
            # ═══════════════════════════════════════════════════════════════
            final_post_ids = set(fts5_post_ids)

            if use_hybrid and self.HYBRID_SAMPLE_RATIO > 0:
                total_count = self._get_total_post_count(expert_id, cutoff_date)
                sample_size = max(self.HYBRID_MIN_SAMPLE, int(total_count * self.HYBRID_SAMPLE_RATIO))
                random_ids = self._get_random_post_ids(expert_id, fts5_post_ids, sample_size, cutoff_date)

                if random_ids:
                    final_post_ids.update(random_ids)
                    logger.info(f"[FTS5 Hybrid] FTS5: {len(fts5_post_ids)}, Random: {len(random_ids)}")

            # Load full Post objects
            posts = self.db.query(Post).filter(Post.post_id.in_(final_post_ids)).all()
            posts_by_id = {p.post_id: p for p in posts}

            # ═══════════════════════════════════════════════════════════════
            # SMART RANKING: BM25 + Time Decay (Gravity)
            # ═══════════════════════════════════════════════════════════════
            now = datetime.utcnow()
            scored_fts5_posts = []
            
            # Normalize BM25 ranks (make them positive, where higher is better)
            # FTS5 rank is negative (e.g., -1.2, -0.5). More negative is better.
            ranks = [row[1] for row in raw_results]
            min_rank = min(ranks) if ranks else 0
            max_rank = max(ranks) if ranks else 0

            for row in raw_results:
                post_id = row[0]
                raw_rank = row[1]
                created_at_str = row[2]

                if post_id not in posts_by_id:
                    continue

                post = posts_by_id[post_id]

                # 1. Normalize BM25 Score (0 to 1, where 1 is the best match in this result set)
                # Since raw_rank is negative and more negative is better:
                # Invert it so higher value means better match.
                # EDGE CASE: Single result = best match, normalize to 1.0
                if max_rank == min_rank:
                    normalized_bm25 = 1.0
                else:
                    normalized_bm25 = (max_rank - raw_rank) / (max_rank - min_rank)
                
                # 2. Calculate Time Decay Penalty (Gravity)
                try:
                    # SQLite stores datetime as string 'YYYY-MM-DD HH:MM:SS' or similar
                    if isinstance(created_at_str, str):
                        # Handle basic ISO format variation SQLite might return
                        clean_str = created_at_str.split('.')[0]
                        created_at = datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        created_at = created_at_str or post.created_at
                except Exception:
                    created_at = post.created_at

                age_days = (now - created_at).days
                age_days = max(0, age_days) # Ensure no negative age
                
                # Gravity formula: freshness_multiplier = 1 / ( (age_in_days / half_life) + 1 )
                # Half-life of 90 days: A post 90 days old loses 50% of its score.
                # A post 365 days old retains only ~20% of its base score.
                HALF_LIFE_DAYS = 90.0
                freshness_multiplier = 1.0 / ((age_days / HALF_LIFE_DAYS) + 1.0)
                
                # 3. Final Combined Score (Base BM25 * Freshness Multiplier)
                # We give BM25 a base floor so even old exact matches aren't completely ignored
                # score = (BM25 * 0.7 + 0.3) * freshness
                final_score = (normalized_bm25 * 0.7 + 0.3) * freshness_multiplier
                
                scored_fts5_posts.append((final_score, post))

            # Sort FTS5 posts by our calculated smart score (Descending: Highest score first)
            scored_fts5_posts.sort(key=lambda x: x[0], reverse=True)
            fts5_posts = [item[1] for item in scored_fts5_posts]
            
            # Random sample posts (sort these purely by date since they have no BM25 rank)
            random_posts = [p for p in posts if p.post_id not in fts5_post_ids]
            random_posts.sort(key=lambda p: p.created_at, reverse=True)

            # Combine: Smart-ranked FTS5 first, then random sample
            sorted_posts = fts5_posts + random_posts

            logger.info(f"[FTS5 Metrics] " + json.dumps({
                "event": "hybrid_hit" if use_hybrid else "hit",
                "expert_id": expert_id,
                "fts5_posts": len(fts5_posts),
                "random_posts": len(random_posts) if use_hybrid else 0,
                "total_posts": len(sorted_posts),
                "query": match_query[:50]
            }, ensure_ascii=False))

            return sorted_posts, True

        except Exception as e:
            logger.error(f"[FTS5 Metrics] " + json.dumps({
                "event": "error",
                "expert_id": expert_id,
                "error": str(e),
                "query": match_query[:100]
            }, ensure_ascii=False))
            return [], False

    def _build_fts5_query(
        self,
        expert_id: str,
        match_query: str,
        cutoff_date: Optional[datetime],
        exclude_media_only: bool
    ) -> str:
        """Build FTS5 SQL query returning both ID, rank, and created_at."""
        cutoff_condition = ""
        if cutoff_date:
            cutoff_condition = "AND p.created_at >= :cutoff_date"

        length_condition = ""
        if exclude_media_only:
            length_condition = "AND LENGTH(COALESCE(p.message_text, '')) > 30"

        # Note: We select f.rank to use it in our custom python sorting
        sql = f"""
        SELECT f.rowid as post_id, f.rank as bm25_rank, p.created_at
        FROM posts_fts f
        JOIN posts p ON p.post_id = f.rowid
        WHERE posts_fts MATCH :match_query
          AND p.expert_id = :expert_id
          {cutoff_condition}
          {length_condition}
        ORDER BY f.rank
        LIMIT :max_results
        """

        return sql

    def _get_total_post_count(
        self,
        expert_id: str,
        cutoff_date: Optional[datetime] = None
    ) -> int:
        """Get total post count for an expert."""
        query = self.db.query(func.count(Post.post_id)).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30
        )

        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)

        return query.scalar() or 0

    def _get_random_post_ids(
        self,
        expert_id: str,
        exclude_ids: set,
        sample_size: int,
        cutoff_date: Optional[datetime] = None
    ) -> set:
        """Get random sample of post IDs (excluding FTS5 results)."""
        query = self.db.query(Post.post_id).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30
        )

        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)

        # Get all candidate IDs
        all_ids = [row[0] for row in query.all()]

        # Exclude FTS5 results
        candidate_ids = [pid for pid in all_ids if pid not in exclude_ids]

        # Random sample
        if len(candidate_ids) <= sample_size:
            return set(candidate_ids)

        return set(random.sample(candidate_ids, sample_size))

    def get_fallback_posts(
        self,
        expert_id: str,
        cutoff_date: Optional[datetime] = None,
        max_posts: Optional[int] = None
    ) -> List[Post]:
        """Get posts using standard retrieval (fallback when FTS5 fails).

        Args:
            expert_id: Expert identifier
            cutoff_date: Optional date filter
            max_posts: Optional limit on posts

        Returns:
            List of Post objects
        """
        query = self.db.query(Post).filter(
            Post.expert_id == expert_id,
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30
        )

        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)

        query = query.order_by(Post.created_at.desc())

        limit = min(max_posts, self.max_results) if max_posts else self.max_results
        query = query.limit(limit)

        posts = query.all()
        logger.info(f"[FTS5 Fallback] Loaded {len(posts)} posts for expert {expert_id}")
        return posts
