"""Comment Group Map service for finding relevant comment groups."""

import asyncio
import json
import os
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import re
import logging
from pathlib import Path
from string import Template

from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from ..models.post import Post
from ..models.comment import Comment
from ..models.database import comment_group_drift
from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError
from ..api.models import get_channel_username
from ..utils.language_utils import prepare_prompt_with_language_instruction

logger = logging.getLogger(__name__)


class CommentGroupMapService:
    """Service for finding relevant GROUPS of comments using Google Gemini.

    Analyzes groups of Telegram comments to find discussions relevant to the query.
    Strategy: Use Google Gemini (Free) with key rotation.
    """

    DEFAULT_CHUNK_SIZE = 20  # Groups per chunk
    DEFAULT_MAX_PARALLEL = 5  # Rate limiting for API calls

    def __init__(
        self,
        model: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_parallel: int = DEFAULT_MAX_PARALLEL
    ):
        """Initialize CommentGroupMapService.

        Args:
            model: Model to use (Gemini)
            chunk_size: Number of comment groups per chunk
            max_parallel: Maximum parallel API calls
        """
        # Initialize Google Client
        self.google_client = None
        try:
            self.google_client = create_google_ai_studio_client()
            if self.google_client:
                logger.info("CommentGroupMapService: Google AI Studio client initialized.")
        except Exception as e:
            logger.warning(f"CommentGroupMapService: Could not initialize Google AI Studio client: {e}")

        self.chunk_size = chunk_size
        self.primary_model = model
        self.max_parallel = max_parallel
        self._prompt_template = self._load_prompt_template()

        logger.info(f"CommentGroupMapService Config: Model={self.primary_model}")

    def _load_prompt_template(self) -> Template:
        """Load the comment group drift prompt template."""
        try:
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "comment_group_drift_prompt.txt"

            if not prompt_path.resolve().is_relative_to(prompt_dir.resolve()):
                raise ValueError(f"Invalid prompt path: {prompt_path}")

            if prompt_path.stat().st_mode & 0o002:
                raise PermissionError("Unsafe prompt file permissions")

            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "$query" not in content or "$groups" not in content:
                raise ValueError("Prompt template missing required placeholders")

            return Template(content)
        except FileNotFoundError:
            logger.error(f"Comment group map prompt template not found at {prompt_path}")
            raise

    def _load_main_source_author_comments(
        self,
        db: Session,
        main_source_ids: List[int],
        expert_id: str
    ) -> List[Dict[str, Any]]:
        """Load author's comments from main_source posts.
        
        These are clarifications the expert made in comments to their own posts
        that were used as main_sources for the answer.
        
        Uses author_id matching: posts have 'channelXXX', comments have 'XXX'.
        """
        if not main_source_ids:
            return []
        
        # Get posts by telegram_message_id
        # Note: main_source_ids come from reduce_results which already processed
        # filtered posts (respecting cutoff_date), so no date filter needed here
        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(main_source_ids),
            Post.expert_id == expert_id
        ).all()
        
        logger.info(f"[{expert_id}] Loading main_source author comments from {len(posts)} posts")
        
        groups = []
        for post in posts:
            # Extract numeric author_id from post (remove 'channel' prefix)
            post_author_id = post.author_id.replace("channel", "") if post.author_id else None
            
            if not post_author_id:
                logger.debug(f"Post {post.telegram_message_id} has no author_id, skipping")
                continue
            
            # Get only author's comments using author_id matching (reliable!)
            author_comments = db.query(Comment).filter(
                Comment.post_id == post.post_id,
                Comment.author_id == post_author_id  # "2273349814" == "2273349814"
            ).order_by(Comment.created_at.desc()).limit(10).all()
            
            if author_comments:
                groups.append({
                    "anchor_post": {
                        "telegram_message_id": post.telegram_message_id,
                        "message_text": post.message_text or "[Media only]",
                        "created_at": post.created_at.isoformat() if post.created_at else "",
                        "author_name": post.author_name or "Unknown",
                        "channel_username": get_channel_username(expert_id)
                    },
                    "drift_topics": ["Author clarification to main source"],
                    "comments_count": len(author_comments),
                    "comments": [
                        {
                            "comment_id": c.comment_id,
                            "comment_text": c.comment_text,
                            "author_name": c.author_name,
                            "created_at": c.created_at.isoformat() if c.created_at else "",
                            "updated_at": c.updated_at.isoformat() if c.updated_at else ""
                        }
                        for c in author_comments
                    ],
                    "is_main_source_clarification": True,  # Flag for synthesis priority
                    "relevance": "HIGH",  # Main source clarifications are always HIGH
                    "reason": "Author's clarification to a main source post",
                    "parent_telegram_message_id": post.telegram_message_id
                })
                logger.debug(f"Found {len(author_comments)} author comments for post {post.telegram_message_id}")
        
        logger.info(f"[{expert_id}] Found {len(groups)} main_source posts with author clarifications")
        return groups

    def _load_main_source_community_comments(
        self,
        db: Session,
        main_source_ids: List[int],
        expert_id: str
    ) -> List[Dict[str, Any]]:
        """Load community comments from main_source posts.
        
        These are comments from community members (not the expert) on the posts
        that were used as main_sources for the answer.
        """
        if not main_source_ids:
            return []
        
        # Get posts by telegram_message_id
        posts = db.query(Post).filter(
            Post.telegram_message_id.in_(main_source_ids),
            Post.expert_id == expert_id
        ).all()
        
        logger.info(f"[{expert_id}] Loading main_source community comments from {len(posts)} posts")
        
        groups = []
        for post in posts:
            # Extract numeric author_id from post (remove 'channel' prefix)
            post_author_id = post.author_id.replace("channel", "") if post.author_id else None
            
            # Get community comments (NOT from author)
            if post_author_id:
                community_comments = db.query(Comment).filter(
                    Comment.post_id == post.post_id,
                    Comment.author_id != post_author_id  # NOT the author
                ).order_by(Comment.created_at.desc()).limit(15).all()
            else:
                # If no author_id, take all comments
                community_comments = db.query(Comment).filter(
                    Comment.post_id == post.post_id
                ).order_by(Comment.created_at.desc()).limit(15).all()
            
            if community_comments:
                groups.append({
                    "anchor_post": {
                        "telegram_message_id": post.telegram_message_id,
                        "message_text": post.message_text or "[Media only]",
                        "created_at": post.created_at.isoformat() if post.created_at else "",
                        "author_name": post.author_name or "Unknown",
                        "channel_username": get_channel_username(expert_id)
                    },
                    "drift_topics": ["Community discussion on main source"],
                    "comments_count": len(community_comments),
                    "comments": [
                        {
                            "comment_id": c.comment_id,
                            "comment_text": c.comment_text,
                            "author_name": c.author_name,
                            "created_at": c.created_at.isoformat() if c.created_at else "",
                            "updated_at": c.updated_at.isoformat() if c.updated_at else ""
                        }
                        for c in community_comments
                    ],
                    "is_main_source_community": True,  # Flag for synthesis
                    "relevance": "HIGH",  # Main source community comments are HIGH priority
                    "reason": "Community discussion on a main source post",
                    "parent_telegram_message_id": post.telegram_message_id
                })
                logger.debug(f"Found {len(community_comments)} community comments for post {post.telegram_message_id}")
        
        logger.info(f"[{expert_id}] Found {len(groups)} main_source posts with community comments")
        return groups

    def _load_drift_groups(
        self,
        db: Session,
        expert_id: str,
        exclude_post_ids: Optional[List[int]] = None,
        cutoff_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Load comment groups with drift from database."""
        print(f"[DEBUG CGS] _load_drift_groups called for expert_id={expert_id}, exclude_post_ids={exclude_post_ids}")  # DEBUG
        
        # Query drift groups with anchor posts
        query = db.query(
            comment_group_drift.c.post_id,
            comment_group_drift.c.drift_topics,
            Post.telegram_message_id,
            Post.message_text,
            Post.created_at,
            Post.author_name
        ).join(
            Post, comment_group_drift.c.post_id == Post.post_id
        ).filter(
            comment_group_drift.c.has_drift == True,
            comment_group_drift.c.expert_id == expert_id
        )

        # Apply date filter if specified
        if cutoff_date:
            query = query.filter(Post.created_at >= cutoff_date)

        if exclude_post_ids:
            validated_ids = [pid for pid in exclude_post_ids if isinstance(pid, int) and pid > 0]
            if validated_ids:
                query = query.filter(Post.telegram_message_id.notin_(validated_ids))

        results = query.all()
        print(f"[DEBUG CGS] DB query returned {len(results)} results")  # DEBUG

        groups = []
        for post_id, drift_topics_json, telegram_msg_id, message_text, created_at, author_name in results:
            if drift_topics_json:
                try:
                    if isinstance(drift_topics_json, bytes):
                        drift_topics_json = drift_topics_json.decode("utf-8")
                    sanitized = re.sub(r'\\(?![ntr"\\/])', '', drift_topics_json)
                    parsed_drift = json.loads(sanitized)

                    if isinstance(parsed_drift, dict) and 'drift_topics' in parsed_drift:
                        drift_topics = parsed_drift['drift_topics']
                    elif isinstance(parsed_drift, list):
                        drift_topics = parsed_drift
                    else:
                        drift_topics = []
                except Exception as e:
                    # Use json_repair as fallback if available, otherwise empty
                    try:
                        from json_repair import repair_json
                        repaired = json.loads(repair_json(drift_topics_json))
                        if isinstance(repaired, dict) and 'drift_topics' in repaired:
                            drift_topics = repaired['drift_topics']
                        elif isinstance(repaired, list):
                            drift_topics = repaired
                        else:
                            drift_topics = []
                    except Exception:
                        drift_topics = []
            else:
                drift_topics = []

            from ..models.comment import Comment
            comments_query = db.query(Comment).filter(Comment.post_id == post_id).all()
            comments = [
                {
                    "comment_id": c.comment_id,
                    "comment_text": c.comment_text,
                    "author_name": c.author_name,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat()
                }
                for c in comments_query
            ]

            groups.append({
                "anchor_post": {
                    "telegram_message_id": telegram_msg_id,
                    "message_text": message_text or "[Media only]",
                    "created_at": created_at.isoformat(),
                    "author_name": author_name or "Unknown",
                    "channel_username": get_channel_username(expert_id)
                },
                "drift_topics": drift_topics,
                "comments_count": len(comments),
                "comments": comments
            })

        return groups

    def _chunk_groups(self, groups: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split comment groups into chunks."""
        chunks = []
        for i in range(0, len(groups), self.chunk_size):
            chunks.append(groups[i:i + self.chunk_size])
        return chunks

    def _format_groups_for_prompt(self, groups: List[Dict[str, Any]]) -> str:
        """Format drift groups for inclusion in the prompt."""
        formatted_groups = []
        for group in groups:
            formatted_groups.append({
                "parent_telegram_message_id": group["anchor_post"]["telegram_message_id"],
                "drift_topics": group["drift_topics"],
                "comments_count": group["comments_count"]
            })

        return json.dumps(formatted_groups, ensure_ascii=False, indent=2)

    async def _call_llm(self, model_name: str, messages: List[Dict[str, str]]):
        """Call Google AI Studio client."""
        if self.google_client:
            return await self.google_client.chat_completions_create(
                model=model_name,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
        raise ValueError("Google Client not initialized")

    def _validate_google_client_availability(self) -> bool:
        """Check if Google AI Studio client is properly initialized."""
        return self.google_client is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
        reraise=True
    )
    async def _process_chunk(
        self,
        chunk: List[Dict[str, Any]],
        query: str,
        chunk_index: int,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process a single chunk of comment groups with Gemini."""
        try:
            if progress_callback:
                await progress_callback({
                    "event_type": "progress",
                    "phase": "comment_groups",
                    "chunk": chunk_index,
                    "status": "processing",
                    "message": f"Analyzing comment groups chunk {chunk_index + 1}"
                })

            # Format the prompt
            groups_formatted = self._format_groups_for_prompt(chunk)

            # Create base prompt
            base_prompt = self._prompt_template.substitute(
                query=query,
                groups=groups_formatted
            )

            # Apply language instruction based on query language
            prompt = prepare_prompt_with_language_instruction(base_prompt, query)

            messages = [
                {"role": "system", "content": "You are analyzing comment groups from Telegram."},
                {"role": "user", "content": prompt}
            ]

            response = None

            # Direct call to Google model
            response = await self._call_llm(self.primary_model, messages)
            logger.info(f"CommentGroups: Successfully used model {self.primary_model}")

            # Parse response
            result = json.loads(response.choices[0].message.content)

            # Add anchor_post and comments back to each group from original chunk data
            chunk_map = {
                group["anchor_post"]["telegram_message_id"]: {
                    "anchor_post": group["anchor_post"],
                    "comments": group["comments"],
                    "comments_count": group["comments_count"]
                }
                for group in chunk
            }

            for group in result.get("relevant_groups", []):
                telegram_msg_id = group.get("parent_telegram_message_id")
                if telegram_msg_id and telegram_msg_id in chunk_map:
                    group["anchor_post"] = chunk_map[telegram_msg_id]["anchor_post"]
                    group["comments"] = chunk_map[telegram_msg_id]["comments"]
                    group["comments_count"] = chunk_map[telegram_msg_id]["comments_count"]

            # Add chunk metadata
            result["chunk_index"] = chunk_index
            result["groups_processed"] = len(chunk)

            if progress_callback:
                await progress_callback({
                    "event_type": "progress",
                    "phase": "comment_groups",
                    "chunk": chunk_index,
                    "status": "completed",
                    "message": f"Comment groups chunk {chunk_index + 1} completed",
                    "relevant_found": len(result.get("relevant_groups", []))
                })

            return result

        except Exception as e:
            logger.error(f"Error processing comment groups chunk {chunk_index}: {str(e)}")
            if progress_callback:
                await progress_callback({
                    "event_type": "error",
                    "phase": "comment_groups",
                    "chunk": chunk_index,
                    "status": "error",
                    "message": f"Error in chunk {chunk_index + 1}: {str(e)}"
                })
            raise

    async def process(
        self,
        query: str,
        db: Session,  # NOTE: Caller MUST manage session lifecycle
        expert_id: str,
        exclude_post_ids: Optional[List[int]] = None,
        main_source_ids: Optional[List[int]] = None,  # NEW: Process author comments from these
        cutoff_date: Optional[datetime] = None,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Process drift groups to find relevant ones.
        
        Args:
            query: User's query
            db: Database session (caller manages lifecycle)
            expert_id: Expert identifier
            exclude_post_ids: Post IDs to exclude from drift search
            main_source_ids: Main source post IDs to extract author comments from (NEW!)
            cutoff_date: Optional cutoff date for filtering drift groups
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of relevant comment groups, with main_source clarifications first
        """
        import time
        phase_start_time = time.time()

        print(f"[DEBUG CGS] process() called for expert_id={expert_id}, main_source_ids={main_source_ids}")  # DEBUG

        # NEW: First load author comments from main_sources (these bypass LLM evaluation)
        main_source_groups = []
        main_source_community_groups = []
        if main_source_ids:
            main_source_groups = self._load_main_source_author_comments(
                db, main_source_ids, expert_id
            )
            logger.info(f"[{expert_id}] Loaded {len(main_source_groups)} main_source clarification groups")
            
            # NEW: Also load community comments from main_sources
            main_source_community_groups = self._load_main_source_community_comments(
                db, main_source_ids, expert_id
            )
            logger.info(f"[{expert_id}] Loaded {len(main_source_community_groups)} main_source community groups")

        # Load drift groups from database (excluding main_sources as before)
        all_groups = self._load_drift_groups(db, expert_id, exclude_post_ids, cutoff_date=cutoff_date)

        print(f"[DEBUG CGS] all_groups loaded: {len(all_groups)}")  # DEBUG

        # If no drift groups but we have main_source groups, return those
        if not all_groups and (main_source_groups or main_source_community_groups):
            combined = main_source_groups + main_source_community_groups
            logger.info(f"[{expert_id}] No drift groups, but returning {len(combined)} main_source groups")
            if progress_callback:
                await progress_callback({
                    "event_type": "phase_complete",
                    "phase": "comment_groups",
                    "status": "completed",
                    "message": f"Found {len(combined)} main source groups"
                })
            return combined

        if not all_groups:
            print(f"[DEBUG CGS] No groups found, returning early")  # DEBUG
            if progress_callback:
                await progress_callback({
                    "event_type": "phase_complete",
                    "phase": "comment_groups",
                    "status": "completed",
                    "message": "No comment groups to analyze"
                })
            return []

        # Split into chunks
        chunks = self._chunk_groups(all_groups)
        total_chunks = len(chunks)

        logger.info(f"[{expert_id}] Comment Groups Phase START: Processing {len(all_groups)} groups in {total_chunks} chunks using {self.primary_model}")

        if progress_callback:
            await progress_callback({
                "event_type": "phase_start",
                "phase": "comment_groups",
                "status": "starting",
                "message": f"Starting comment groups analysis: {len(all_groups)} groups in {total_chunks} chunks",
                "total_chunks": total_chunks
            })

        # Process chunks in parallel
        parallel_limit = self.max_parallel if self.max_parallel is not None else total_chunks
        semaphore = asyncio.Semaphore(parallel_limit)

        async def process_with_semaphore(chunk, index):
            async with semaphore:
                return await self._process_chunk(chunk, query, index, progress_callback)

        tasks = [
            process_with_semaphore(chunk, i)
            for i, chunk in enumerate(chunks)
        ]

        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_relevant_groups = []
        chunks_with_errors = []

        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                logger.error(f"Comment groups chunk {i} failed: {result}")
                chunks_with_errors.append(i)
            else:
                # Validate each group has anchor_post before adding
                groups = result.get("relevant_groups", [])
                for group in groups:
                    if not group.get("anchor_post"):
                        logger.error(f"Group missing anchor_post in chunk {i}: {group}")
                        continue
                    all_relevant_groups.append(group)

        # Filter HIGH relevance only
        relevant_groups = [
            g for g in all_relevant_groups
            if g.get("relevance") == "HIGH"
        ]

        # Sort by relevance THEN by Freshness (Date of anchor post)
        # Strategy: Python sort is stable.

        # 1. Global Sort: Date Descending (Newest discussions first)
        relevant_groups.sort(key=lambda x: x["anchor_post"].get("created_at", ""), reverse=True)

        # 2. Stable Sort: Relevance Ascending (HIGH=0, MEDIUM=1)
        relevance_order = {"HIGH": 0, "MEDIUM": 1}
        relevant_groups.sort(key=lambda x: relevance_order.get(x.get("relevance", "LOW"), 2))

        # NEW: Combine main_source clarifications (first), then community, then drift groups
        # Priority: author clarifications > community on main sources > drift groups
        final_groups = main_source_groups + main_source_community_groups + relevant_groups

        # Log phase completion with timing
        duration_ms = int((time.time() - phase_start_time) * 1000)
        logger.info(
            f"[{expert_id}] Comment Groups Phase END: {duration_ms}ms, "
            f"found {len(main_source_groups)} author clarifications + "
            f"{len(main_source_community_groups)} community on main sources + "
            f"{len(relevant_groups)} drift groups = {len(final_groups)} total"
        )

        if progress_callback:
            await progress_callback({
                "event_type": "phase_complete",
                "phase": "comment_groups",
                "status": "completed",
                "message": f"Found {len(final_groups)} relevant comment groups ({len(main_source_groups)} author + {len(main_source_community_groups)} community from main sources)"
            })

        return final_groups