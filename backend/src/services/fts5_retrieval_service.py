"""FTS5 Retrieval Service for Super-Passport Search.

Provides full-text search capabilities using SQLite FTS5 for pre-filtering
posts before the Map Phase, reducing token usage and latency.
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.post import Post
from ..config import MAX_FTS_RESULTS

logger = logging.getLogger(__name__)


class FTS5RetrievalService:
    """Service for retrieving posts using FTS5 full-text search.

    Pre-filters posts using SQLite FTS5 index before Map Phase.
    Falls back to standard retrieval if FTS5 returns no results.
    """

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
        exclude_media_only: bool = True
    ) -> Tuple[List[Post], bool]:
        """Search posts using FTS5 MATCH query.

        Args:
            expert_id: Expert identifier
            match_query: FTS5 MATCH query string (e.g., "kubernetes OR кубер*")
            cutoff_date: Optional date filter (only posts >= this date)
            exclude_media_only: Exclude posts with <= 30 characters

        Returns:
            Tuple of (posts list, used_fts5 flag)
            used_fts5 is True if FTS5 returned results, False if fallback was used
        """
        try:
            # Build FTS5 query
            sql = self._build_fts5_query(expert_id, match_query, cutoff_date, exclude_media_only)

            result = self.db.execute(text(sql), {
                "expert_id": expert_id,
                "match_query": match_query,
                "cutoff_date": cutoff_date.isoformat() if cutoff_date else None,
                "max_results": self.max_results
            })

            post_ids = [row[0] for row in result.fetchall()]

            if post_ids:
                # Load full Post objects
                posts = self.db.query(Post).filter(Post.post_id.in_(post_ids)).all()

                # Sort by post_ids order (FTS5 rank)
                post_map = {p.post_id: p for p in posts}
                sorted_posts = [post_map[pid] for pid in post_ids if pid in post_map]

                logger.info(f"[FTS5] Found {len(sorted_posts)} posts for expert {expert_id} with query: {match_query[:50]}...")
                return sorted_posts, True
            else:
                logger.info(f"[FTS5] No results for expert {expert_id}, will use fallback")
                return [], False

        except Exception as e:
            logger.warning(f"[FTS5] Search failed for expert {expert_id}: {e}")
            return [], False

    def _build_fts5_query(
        self,
        expert_id: str,
        match_query: str,
        cutoff_date: Optional[datetime],
        exclude_media_only: bool
    ) -> str:
        """Build FTS5 SQL query.

        Note: FTS5 queries use special syntax, we need to be careful with parameters.
        """
        # FTS5 MATCH clause - we interpolate carefully (match_query should be sanitized by AIScout)
        # Using parameter binding for non-MATCH parts

        cutoff_condition = ""
        if cutoff_date:
            cutoff_condition = "AND p.created_at >= :cutoff_date"

        length_condition = ""
        if exclude_media_only:
            length_condition = "AND LENGTH(COALESCE(p.message_text, '')) > 30"

        sql = f"""
        SELECT f.rowid as post_id
        FROM posts_fts f
        JOIN posts p ON p.post_id = f.rowid
        WHERE f.posts_fts MATCH :match_query
          AND p.expert_id = :expert_id
          {cutoff_condition}
          {length_condition}
        ORDER BY f.rank, p.created_at DESC
        LIMIT :max_results
        """

        return sql

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
        from sqlalchemy import func

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
