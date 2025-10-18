"""Simplified Resolve service - enriches posts by following author's links without GPT evaluation."""

import logging
from typing import List, Dict, Any, Optional, Callable, Set
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..models.post import Post
from ..models.link import Link, LinkType
from ..models.base import SessionLocal

logger = logging.getLogger(__name__)


class SimpleResolveService:
    """Simplified Resolve service that trusts author's linking decisions.

    Key principle: The author already made the cognitive work of deciding what to link.
    We simply follow these links to depth 1, no GPT evaluation needed.
    """

    def __init__(self):
        """Initialize SimpleResolveService - no API key needed!"""
        pass

    def _fetch_posts_by_telegram_ids(
        self,
        db: Session,
        telegram_message_ids: List[int],
        expert_id: str
    ) -> Dict[int, Post]:
        """Fetch posts from database by telegram_message_id.

        Args:
            db: Database session
            telegram_message_ids: List of telegram message IDs
            expert_id: Expert identifier to filter posts

        Returns:
            Dictionary mapping telegram_message_id to Post object
        """
        if not telegram_message_ids:
            return {}

        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(telegram_message_ids),
            Post.expert_id == expert_id
        ).all()

        return {post.telegram_message_id: post for post in posts}

    def _get_linked_posts(
        self,
        db: Session,
        initial_post_ids: Set[int],
        expert_id: str
    ) -> Set[int]:
        """Get all posts linked at depth 1 from initial posts.

        Philosophy: Author's links are intentional - if they linked it, it's relevant.
        98.9% of links are MENTION type (thematic connections).

        Args:
            db: Database session
            initial_post_ids: Set of telegram_message_ids to expand from
            expert_id: Expert identifier to filter posts

        Returns:
            Set of all linked telegram_message_ids (including initial)
        """
        if not initial_post_ids:
            return set()

        # Get Post objects to get their database IDs
        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(initial_post_ids),
            Post.expert_id == expert_id
        ).all()

        if not posts:
            logger.warning(f"No posts found for telegram_ids: {initial_post_ids}")
            return initial_post_ids

        post_id_to_telegram = {p.post_id: p.telegram_message_id for p in posts}
        db_post_ids = list(post_id_to_telegram.keys())

        # Get ALL links where our posts are source or target
        links = db.query(Link).filter(
            or_(
                Link.source_post_id.in_(db_post_ids),
                Link.target_post_id.in_(db_post_ids)
            )
        ).all()

        linked_telegram_ids = set(initial_post_ids)

        # Collect only NEW linked post IDs (not in initial set)
        linked_db_ids = set()
        for link in links:
            # Only add posts that are NOT in our initial set
            if link.source_post_id not in db_post_ids:
                linked_db_ids.add(link.source_post_id)
            if link.target_post_id not in db_post_ids:
                linked_db_ids.add(link.target_post_id)

        # Convert database IDs back to telegram_message_ids
        if linked_db_ids:
            linked_posts = db.query(Post).filter(
                Post.post_id.in_(linked_db_ids),
                Post.expert_id == expert_id
            ).all()

            for post in linked_posts:
                linked_telegram_ids.add(post.telegram_message_id)

        logger.info(
            f"[{expert_id}] Expanded {len(initial_post_ids)} posts to {len(linked_telegram_ids)} "
            f"(+{len(linked_telegram_ids) - len(initial_post_ids)} linked posts)"
        )

        return linked_telegram_ids

    async def process(
        self,
        relevant_posts: List[Dict[str, Any]],
        query: str,  # Kept for interface compatibility
        expert_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process and enrich posts with linked context at depth 1.

        Args:
            relevant_posts: List of relevant post data from Map phase
            query: User's query (not used in simplified version)
            expert_id: Expert identifier to filter posts
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with enriched post data
        """
        import time
        phase_start_time = time.time()

        if not relevant_posts:
            return {
                "enriched_posts": [],
                "links_followed": 0,
                "additional_posts": 0,
                "summary": "No posts to enrich"
            }

        # Extract telegram_message_ids from relevant posts
        relevant_ids = [p["telegram_message_id"] for p in relevant_posts]

        logger.info(f"[{expert_id}] Resolve Phase START: Enriching {len(relevant_ids)} relevant posts with linked context")

        if progress_callback:
            await progress_callback({
                "phase": "resolve",
                "status": "starting",
                "message": f"Expanding {len(relevant_ids)} posts with author's links",
                "processed": 0,
                "total": len(relevant_ids)
            })

        # Create database session
        db = SessionLocal()
        try:
            # Get all linked posts at depth 1 - NO LIMITS!
            all_post_ids = self._get_linked_posts(
                db,
                set(relevant_ids),
                expert_id
            )

            # Fetch all posts (original + linked)
            posts_map = self._fetch_posts_by_telegram_ids(
                db, list(all_post_ids), expert_id
            )

            # Build enriched result
            enriched_posts = []

            # First add original relevant posts with their scores
            for post_data in relevant_posts:
                tid = post_data["telegram_message_id"]
                if tid in posts_map:
                    post = posts_map[tid]
                    enriched_posts.append({
                        "telegram_message_id": tid,
                        "relevance": post_data.get("relevance", "MEDIUM"),
                        "reason": post_data.get("reason", ""),
                        "is_original": True,
                        "content": post.message_text,
                        "author": post.author_name,
                        "created_at": post.created_at.isoformat() if post.created_at else None
                    })

            # Then add ALL linked posts
            linked_count = 0
            for tid in all_post_ids:
                if tid not in relevant_ids and tid in posts_map:
                    post = posts_map[tid]
                    enriched_posts.append({
                        "telegram_message_id": tid,
                        "relevance": "CONTEXT",
                        "reason": "Author-linked context (depth 1)",
                        "is_original": False,
                        "content": post.message_text,
                        "author": post.author_name,
                        "created_at": post.created_at.isoformat() if post.created_at else None
                    })
                    linked_count += 1

            summary = (
                f"Enriched {len(relevant_ids)} posts with {linked_count} author-linked posts. "
                f"Total context: {len(enriched_posts)} posts."
            )

            # Log phase completion with timing
            duration_ms = int((time.time() - phase_start_time) * 1000)
            logger.info(
                f"[{expert_id}] Resolve Phase END: {duration_ms}ms, "
                f"expanded {len(relevant_ids)} posts to {len(enriched_posts)} posts (+{linked_count} linked)"
            )

            if progress_callback:
                await progress_callback({
                    "phase": "resolve",
                    "status": "completed",
                    "message": "Context expansion completed",
                    "summary": summary,
                    "processed": len(all_post_ids),
                    "total": len(all_post_ids)
                })

            return {
                "enriched_posts": enriched_posts,
                "links_followed": linked_count,
                "additional_posts": linked_count,
                "summary": summary
            }

        finally:
            db.close()