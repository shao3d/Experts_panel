"""Resolve service for enriching posts with linked context."""

import json
import logging
from typing import List, Dict, Any, Optional, Callable, Set
from collections import defaultdict, deque
from pathlib import Path
from string import Template

from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import or_
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.post import Post
from ..models.link import Link, LinkType
from ..models.base import SessionLocal
from .openrouter_adapter import create_openrouter_client, convert_model_name

logger = logging.getLogger(__name__)


class ResolveService:
    """Service for the Resolve phase of the Map-Resolve-Reduce pipeline.

    Enriches relevant posts by following database links to provide
    complete context, using GPT-4o-mini to evaluate link importance.
    """

    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_MAX_DEPTH = 2
    MAX_ADDITIONAL_POSTS = 10  # Limit to prevent explosion

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_depth: int = DEFAULT_MAX_DEPTH
    ):
        """Initialize ResolveService.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (default gpt-4o-mini)
            max_depth: Maximum depth for link traversal (default 2)
        """
        self.client = create_openrouter_client(api_key=api_key)
        self.model = convert_model_name(model)
        self.max_depth = max_depth
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template:
        """Load the resolve phase prompt template."""
        try:
            # Use relative path from current file location
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "resolve_prompt.txt"

            with open(prompt_path, "r", encoding="utf-8") as f:
                return Template(f.read())
        except FileNotFoundError:
            logger.error(f"Resolve prompt template not found at {prompt_path}")
            raise

    def _get_links_for_posts(
        self,
        db: Session,
        post_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """Get all links involving the given posts from database.

        Args:
            db: Database session
            post_ids: List of post IDs to find links for

        Returns:
            List of link dictionaries
        """
        # Query for links where posts are either source or target
        links = db.query(Link).filter(
            or_(
                Link.source_post_id.in_(post_ids),
                Link.target_post_id.in_(post_ids)
            )
        ).all()

        # Format links for prompt
        formatted_links = []
        for link in links:
            formatted_links.append({
                "from_post_id": link.source_post_id,
                "to_post_id": link.target_post_id,
                "link_type": link.link_type.upper() if hasattr(link.link_type, 'upper') else link.link_type
            })

        return formatted_links

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def _evaluate_links(
        self,
        query: str,
        relevant_post_ids: List[int],
        links: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Use GPT-4o-mini to evaluate which links are important.

        Args:
            query: User's query
            relevant_post_ids: IDs of already relevant posts
            links: Available links from database
            progress_callback: Optional callback for progress updates

        Returns:
            GPT evaluation result
        """
        if progress_callback:
            await progress_callback({
                "phase": "resolve",
                "status": "evaluating",
                "message": f"Evaluating {len(links)} links for importance"
            })

        # Format the prompt
        prompt = self._prompt_template.substitute(
            query=query,
            relevant_post_ids=json.dumps(relevant_post_ids),
            links=json.dumps(links, ensure_ascii=False, indent=2)
        )

        # Call OpenAI API
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that evaluates link importance."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        # Parse response
        result = json.loads(response.choices[0].message.content)

        if progress_callback:
            await progress_callback({
                "phase": "resolve",
                "status": "evaluated",
                "message": f"Found {len(result.get('important_post_ids', []))} important linked posts",
                "expand_depth": result.get("expand_depth", 1)
            })

        return result

    def _fetch_posts_by_telegram_ids(
        self,
        db: Session,
        telegram_message_ids: List[int]
    ) -> Dict[int, Post]:
        """Fetch posts from database by telegram_message_id.

        Args:
            db: Database session
            telegram_message_ids: List of telegram message IDs

        Returns:
            Dictionary mapping telegram_message_id to Post object
        """
        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(telegram_message_ids)
        ).all()

        return {post.telegram_message_id: post for post in posts}

    def _expand_links(
        self,
        db: Session,
        initial_post_ids: Set[int],
        depth: int
    ) -> Set[int]:
        """Expand posts by following links to specified depth.

        Args:
            db: Database session
            initial_post_ids: Starting set of telegram_message_ids
            depth: How many levels to expand

        Returns:
            Expanded set of telegram_message_ids
        """
        visited = set(initial_post_ids)
        current_level = set(initial_post_ids)

        for level in range(depth):
            if not current_level:
                break

            # Stop if we've collected too many posts
            if len(visited) >= self.MAX_ADDITIONAL_POSTS + len(initial_post_ids):
                logger.warning(f"Stopping expansion at level {level}, reached post limit")
                break

            # Get posts by telegram_message_id
            posts = db.query(Post).filter(
                Post.telegram_message_id.in_(current_level)
            ).all()

            if not posts:
                break

            # Get post_ids for database queries
            post_ids = [p.post_id for p in posts]

            # Find all links for current level posts
            links = db.query(Link).filter(
                or_(
                    Link.source_post_id.in_(post_ids),
                    Link.target_post_id.in_(post_ids)
                )
            ).all()

            next_level = set()
            for link in links:
                # Get connected post IDs
                source_post = db.query(Post).filter(Post.post_id == link.source_post_id).first()
                target_post = db.query(Post).filter(Post.post_id == link.target_post_id).first()

                if source_post and source_post.telegram_message_id not in visited:
                    next_level.add(source_post.telegram_message_id)
                if target_post and target_post.telegram_message_id not in visited:
                    next_level.add(target_post.telegram_message_id)

                # Stop if getting too many
                if len(visited) + len(next_level) >= self.MAX_ADDITIONAL_POSTS + len(initial_post_ids):
                    break

            visited.update(next_level)
            current_level = next_level
            logger.info(f"Depth {level + 1}: Added {len(next_level)} posts")

        return visited

    async def process(
        self,
        relevant_posts: List[Dict[str, Any]],
        query: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process and enrich posts with linked context.

        Args:
            relevant_posts: List of relevant post data from Map phase
            query: User's query
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with enriched post data
        """
        if not relevant_posts:
            return {
                "enriched_posts": [],
                "links_followed": 0,
                "depth_reached": 0,
                "summary": "No posts to enrich"
            }

        # Extract telegram_message_ids from relevant posts
        relevant_ids = [p["telegram_message_id"] for p in relevant_posts]

        logger.info(f"Enriching {len(relevant_ids)} relevant posts with linked context")

        if progress_callback:
            await progress_callback({
                "phase": "resolve",
                "status": "starting",
                "message": f"Starting Resolve phase for {len(relevant_ids)} posts"
            })

        # Create database session
        db = SessionLocal()
        try:
            # Get posts by telegram_message_id to get their post_ids
            posts_map = self._fetch_posts_by_telegram_ids(db, relevant_ids)
            post_ids = [p.post_id for p in posts_map.values()]

            # Get all links involving these posts
            links = self._get_links_for_posts(db, post_ids)

            if not links:
                logger.info("No links found for relevant posts, enriching with content")
                # Enrich posts with content from database
                enriched = []
                for post_data in relevant_posts:
                    tid = post_data.get("telegram_message_id")
                    post = db.query(Post).filter(Post.telegram_message_id == tid).first()
                    if post:
                        enriched.append({
                            "telegram_message_id": tid,
                            "relevance": post_data.get("relevance", "MEDIUM"),
                            "reason": post_data.get("reason", ""),
                            "is_original": True,
                            "content": post.message_text,
                            "author": post.author_name,
                            "created_at": post.created_at.isoformat() if post.created_at else None
                        })
                    else:
                        enriched.append(post_data)

                return {
                    "enriched_posts": enriched,
                    "links_followed": 0,
                    "depth_reached": 0,
                    "summary": "No links found to follow"
                }

            # Use GPT to evaluate which links are important
            evaluation = await self._evaluate_links(
                query, relevant_ids, links, progress_callback
            )

            important_ids = evaluation.get("important_post_ids", [])
            expand_depth = min(evaluation.get("expand_depth", 1), self.max_depth)

            if not important_ids:
                logger.info("No important links identified, enriching with content")
                # Enrich posts with content from database
                enriched = []
                for post_data in relevant_posts:
                    tid = post_data.get("telegram_message_id")
                    post = db.query(Post).filter(Post.telegram_message_id == tid).first()
                    if post:
                        enriched.append({
                            "telegram_message_id": tid,
                            "relevance": post_data.get("relevance", "MEDIUM"),
                            "reason": post_data.get("reason", ""),
                            "is_original": True,
                            "content": post.message_text,
                            "author": post.author_name,
                            "created_at": post.created_at.isoformat() if post.created_at else None
                        })
                    else:
                        enriched.append(post_data)

                return {
                    "enriched_posts": enriched,
                    "links_followed": 0,
                    "depth_reached": 0,
                    "summary": "No important links identified"
                }

            if progress_callback:
                await progress_callback({
                    "phase": "resolve",
                    "status": "expanding",
                    "message": f"Expanding {len(important_ids)} important posts to depth {expand_depth}"
                })

            # Expand posts to specified depth
            all_post_ids = self._expand_links(
                db,
                set(relevant_ids + important_ids),
                expand_depth
            )

            # Fetch all expanded posts
            expanded_posts_map = self._fetch_posts_by_telegram_ids(db, list(all_post_ids))

            # Build enriched result
            enriched_posts = []

            # First add original relevant posts with their scores
            for post_data in relevant_posts:
                tid = post_data["telegram_message_id"]
                if tid in expanded_posts_map:
                    post = expanded_posts_map[tid]
                    enriched_posts.append({
                        "telegram_message_id": tid,
                        "relevance": post_data.get("relevance", "MEDIUM"),
                        "reason": post_data.get("reason", ""),
                        "is_original": True,
                        "content": post.message_text,
                        "author": post.author_name,
                        "created_at": post.created_at.isoformat() if post.created_at else None
                    })

            # Then add linked posts
            linked_count = 0
            for tid in all_post_ids:
                if tid not in relevant_ids and tid in expanded_posts_map:
                    post = expanded_posts_map[tid]
                    enriched_posts.append({
                        "telegram_message_id": tid,
                        "relevance": "CONTEXT",
                        "reason": "Linked context post",
                        "is_original": False,
                        "content": post.message_text,
                        "author": post.author_name,
                        "created_at": post.created_at.isoformat() if post.created_at else None
                    })
                    linked_count += 1

            summary = (
                f"Enriched {len(relevant_ids)} posts with {linked_count} linked posts. "
                f"Expanded to depth {expand_depth}. "
                f"Total context: {len(enriched_posts)} posts."
            )

            if progress_callback:
                await progress_callback({
                    "phase": "resolve",
                    "status": "completed",
                    "message": "Resolve phase completed",
                    "summary": summary
                })

            return {
                "enriched_posts": enriched_posts,
                "links_followed": len(links),
                "depth_reached": expand_depth,
                "additional_posts": linked_count,
                "summary": summary
            }

        finally:
            db.close()