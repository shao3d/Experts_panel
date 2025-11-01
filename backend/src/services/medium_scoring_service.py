"""Medium posts scoring service for hybrid reranking with GPT-4o-mini."""

import json
import logging
import os
import re
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from string import Template

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from .openrouter_adapter import create_openrouter_client, convert_model_name
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language

logger = logging.getLogger(__name__)


class MediumScoringService:
    """Service for scoring MEDIUM relevance posts using Qwen2.5-72B.

    Implements hybrid approach: LLM scores all MEDIUM posts 0.0-1.0,
    code selects posts with score >= 0.7 (max 5 posts by highest score).
    """

    DEFAULT_MODEL = os.getenv("MODEL_ANALYSIS", "qwen/qwen-2.5-32b-instruct")
    # Configurable via environment variables
    SCORE_THRESHOLD = float(os.getenv("MEDIUM_SCORE_THRESHOLD", "0.7"))
    MAX_SELECTED_POSTS = int(os.getenv("MEDIUM_MAX_SELECTED_POSTS", "5"))
    MAX_MEDIUM_POSTS = int(os.getenv("MEDIUM_MAX_POSTS", "50"))  # Memory limit

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        """Initialize MediumScoringService.

        Args:
            api_key: OpenAI API key
            model: Model to use (default qwen-2.5-72b)
        """
        # Mask API key for logging
        self.api_key_masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        self.client = create_openrouter_client(api_key=api_key)
        self.model = convert_model_name(model)
        self.score_threshold = self.SCORE_THRESHOLD
        self.max_selected_posts = self.MAX_SELECTED_POSTS
        self.max_medium_posts = self.MAX_MEDIUM_POSTS
        self._prompt_template = self._load_prompt_template()

    def _sanitize_text(self, text: str) -> str:
        """Remove invalid escape sequences from text.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text safe for JSON
        """
        if not text:
            return text
        # Remove invalid escape sequences, keep only valid JSON escapes
        return re.sub(r'\\(?![ntr"\\/])', '', text)

    def _parse_text_response(self, raw_content: str, medium_posts: List[Dict[str, Any]], expert_id: str) -> Dict[str, Any]:
        """Parse markdown text response from model and convert to JSON format.

        Args:
            raw_content: Raw text response from model
            medium_posts: List of medium posts that were scored
            expert_id: Expert identifier for logging

        Returns:
            Dictionary in expected format with scored_posts
        """
        logger.info(f"[{expert_id}] Parsing markdown text response from model")

        # Split response into individual post sections by looking for "POST" markers
        sections = raw_content.split("=== POST")

        scored_posts = []

        # Extract information from each section
        for section in sections:
            if not section.strip():  # Skip empty sections
                continue

            post_data = {
                "telegram_message_id": None,
                "score": 0.0,
                "reason": ""
            }

            # Use regex to be more robust against formatting variations
            id_match = re.search(r'ID:\s*(\d+)', section, re.IGNORECASE)
            score_match = re.search(r'Score:\s*([0-9.]+)', section, re.IGNORECASE)
            reason_match = re.search(r'Reason:(.*)', section, re.IGNORECASE | re.DOTALL)

            if id_match:
                try:
                    post_data["telegram_message_id"] = int(id_match.group(1).strip())
                except (ValueError, TypeError):
                    logger.warning(f"[{expert_id}] Could not parse post ID from: {id_match.group(1)}")
                    post_data["telegram_message_id"] = None

            if score_match:
                try:
                    post_data["score"] = float(score_match.group(1).strip())
                except ValueError:
                    logger.warning(f"[{expert_id}] Could not parse score from: {score_match.group(1)}")
                    post_data["score"] = 0.0

            if reason_match:
                post_data["reason"] = reason_match.group(1).strip()

            # Only add if we have a valid ID
            if post_data["telegram_message_id"] is not None:
                scored_posts.append(post_data)

        # Match scored posts with input posts and validate IDs
        valid_scored_posts = []
        input_ids = {post["telegram_message_id"] for post in medium_posts}

        for scored_post in scored_posts:
            post_id = scored_post["telegram_message_id"]
            if post_id in input_ids:
                valid_scored_posts.append(scored_post)
            else:
                logger.warning(f"[{expert_id}] Scored post ID {post_id} not found in input posts")

        # Ensure all input posts have scores (add default scores if missing)
        for post in medium_posts:
            post_id = post["telegram_message_id"]
            if not any(sp.get("telegram_message_id") == post_id for sp in valid_scored_posts):
                logger.warning(f"[{expert_id}] No score found for input post {post_id}, using default 0.0")
                valid_scored_posts.append({
                    "telegram_message_id": post_id,
                    "score": 0.0,
                    "reason": "Not scored by model"
                })

        logger.info(f"[{expert_id}] Parsed {len(valid_scored_posts)} scored posts from text response")

        return {"scored_posts": valid_scored_posts}

    def _load_prompt_template(self) -> Template:
        """Load medium scoring prompt template."""
        try:
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "medium_scoring_prompt.txt"

            # SECURITY: Prevent path traversal attacks
            if not prompt_path.resolve().is_relative_to(prompt_dir.resolve()):
                raise ValueError(f"Invalid prompt path: {prompt_path}")

            # SECURITY: Check file permissions (not world-writable)
            if prompt_path.stat().st_mode & 0o002:
                logger.error(f"Prompt file is world-writable: {prompt_path}")
                raise PermissionError("Unsafe prompt file permissions")

            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Validate required placeholders
            if "$query" not in content or "$high_posts" not in content or "$medium_posts" not in content:
                raise ValueError("Prompt template missing required placeholders")

            return Template(content)
        except FileNotFoundError:
            logger.error(f"Medium scoring prompt template not found at {prompt_path}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
        reraise=True
    )
    async def _score_medium_posts(
        self,
        medium_posts: List[Dict[str, Any]],
        high_posts_context: str,
        query: str,
        expert_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Score MEDIUM posts using Qwen2.5-72B.

        Args:
            medium_posts: List of MEDIUM relevance posts to score
            high_posts_context: JSON context of HIGH relevance posts
            query: User's query
            expert_id: Expert identifier
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with scored posts
        """
        if progress_callback:
            await progress_callback({
                "phase": "medium_scoring",
                "status": "scoring",
                "message": f"Scoring {len(medium_posts)} MEDIUM posts for relevance",
                "processed": 0,
                "total": len(medium_posts),
                "expert_id": expert_id
            })

        # Format medium posts for prompt with markdown structure
        medium_posts_text = ""
        for i, post in enumerate(medium_posts):
            medium_posts_text += f"""
=== POST {i+1} ===
ID: {post["telegram_message_id"]}
Content: {post.get('content', '')}
Author: {post.get('author', '')}
Created: {post.get('created_at', '')}
"""

        # Note: Qwen will receive this as plain text, not JSON

        # Log the actual data being sent to Qwen2.5-72B for debugging
        logger.info(f"[{expert_id}] Sending {len(medium_posts)} posts to Qwen2.5-72B:")
        for i, post in enumerate(medium_posts[:3]):  # Log first 3 posts as example
            logger.info(f"[{expert_id}] Post {i+1}: ID={post['telegram_message_id']}, content_len={len(post.get('content', ''))}")

        # Create base prompt
        base_prompt = self._prompt_template.substitute(
            query=query,
            high_posts=high_posts_context,
            medium_posts=medium_posts_text
        )

        # Debug logging to check variable substitution
        logger.info(f"[{expert_id}] DEBUG: Prompt template substitution completed")
        logger.info(f"[{expert_id}] DEBUG: Query length: {len(query)}")
        logger.info(f"[{expert_id}] DEBUG: High posts context length: {len(high_posts_context)}")
        logger.info(f"[{expert_id}] DEBUG: Medium posts text length: {len(medium_posts_text)}")
        logger.info(f"[{expert_id}] DEBUG: Final prompt preview (first 500 chars): {base_prompt[:500]}")

        # Apply language instruction based on query language
        prompt = prepare_prompt_with_language_instruction(base_prompt, query)

        # Prepare enhanced system message with language instruction
        enhanced_system = prepare_system_message_with_language(
            "You are analyzing MEDIUM-relevance posts to determine which ones should complement HIGH-relevance posts.",
            query
        )

        # Call API
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        # Parse response with enhanced validation
        raw_content = response.choices[0].message.content

        # Log Qwen2.5-72B response for debugging
        logger.info(f"[{expert_id}] Qwen2.5-72B response: {raw_content}")

        # Validate non-empty response
        if not raw_content or not raw_content.strip():
            logger.error(f"[{expert_id}] Empty response from Qwen2.5-72B for medium scoring")
            raise ValueError("Empty LLM response for medium scoring")

        # Parse text response and convert to expected JSON format
        result = self._parse_text_response(raw_content, medium_posts, expert_id)

        # Validate response structure
        if not isinstance(result, dict):
            logger.error(f"[{expert_id}] Qwen2.5-72B returned non-dict response: {type(result)}")
            raise ValueError(f"Expected dict response, got {type(result)}")

        if "scored_posts" not in result:
            logger.error(f"[{expert_id}] Qwen2.5-72B response missing 'scored_posts' field: {list(result.keys())}")
            raise ValueError("Missing 'scored_posts' field in LLM response")

        if not isinstance(result["scored_posts"], list):
            logger.error(f"[{expert_id}] Qwen2.5-72B 'scored_posts' not list: {type(result['scored_posts'])}")
            raise ValueError(f"Expected 'scored_posts' to be list, got {type(result['scored_posts'])}")

        # Log scored posts count for validation
        scored_posts_count = len(result["scored_posts"])
        expected_count = len(medium_posts)
        logger.info(f"[{expert_id}] Qwen2.5-72B scored {scored_posts_count}/{expected_count} posts")

        if progress_callback:
            await progress_callback({
                "phase": "medium_scoring",
                "status": "completed",
                "message": f"Scored {len(medium_posts)} MEDIUM posts",
                "processed": len(medium_posts),
                "total": len(medium_posts),
                "expert_id": expert_id
            })

        return result

    async def score_medium_posts(
        self,
        medium_posts: List[Dict[str, Any]],
        high_posts_context: str,
        query: str,
        expert_id: str,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Score MEDIUM posts and filter by threshold and limit.

        Args:
            medium_posts: List of MEDIUM relevance posts from Map phase
            high_posts_context: JSON context of HIGH relevance posts
            query: User's query
            expert_id: Expert identifier
            progress_callback: Optional callback for progress updates

        Returns:
            List of scored and filtered MEDIUM posts (max 5 with score >= 0.7)
        """
        if not medium_posts:
            logger.info(f"[{expert_id}] No MEDIUM posts to score")
            return []

        # Memory protection: limit number of medium posts
        if len(medium_posts) > self.max_medium_posts:
            logger.warning(
                f"[{expert_id}] Too many MEDIUM posts ({len(medium_posts)}), "
                f"limiting to {self.max_medium_posts} for memory protection"
            )
            medium_posts = medium_posts[:self.max_medium_posts]

        logger.info(f"[{expert_id}] Medium Scoring Phase START: Scoring {len(medium_posts)} MEDIUM posts")

        # Debug logging to check received posts
        logger.info(f"[{expert_id}] DEBUG: Received {len(medium_posts)} medium posts for scoring")
        for i, post in enumerate(medium_posts[:2]):  # Log first 2 posts with content
            logger.info(f"[{expert_id}] DEBUG: Post {i+1} data: ID={post.get('telegram_message_id')}, "
                       f"content_len={len(post.get('content', ''))}, "
                       f"content_preview='{post.get('content', '')[:100]}'")

        # Score all MEDIUM posts
        try:
            scoring_result = await self._score_medium_posts(
                medium_posts=medium_posts,
                high_posts_context=high_posts_context,
                query=query,
                expert_id=expert_id,
                progress_callback=progress_callback
            )
        except Exception as e:
            logger.error(f"[{expert_id}] Qwen2.5-72B medium scoring failed (API key: {self.api_key_masked}): {e}")
            # Fallback: return empty list (graceful degradation)
            if progress_callback:
                await progress_callback({
                    "phase": "medium_scoring",
                    "status": "error",
                    "message": f"Qwen2.5-72B scoring failed, using fallback: {str(e)}"
                })
            return []

        # Process scored posts
        scored_posts_data = scoring_result.get("scored_posts", [])
        scored_posts = []

        # Merge original post data with scores
        for post_data in medium_posts:
            post_id = post_data["telegram_message_id"]

            # Find matching score data
            score_info = next(
                (s for s in scored_posts_data if s.get("telegram_message_id") == post_id),
                None
            )

            if score_info:
                scored_posts.append({
                    "telegram_message_id": post_id,
                    "relevance": "MEDIUM",  # Keep original classification
                    "reason": post_data.get("reason", ""),  # Preserve original reason
                    "content": post_data.get("content", ""),
                    "author": post_data.get("author", ""),
                    "created_at": post_data.get("created_at", ""),
                    "score": score_info.get("score", 0.0),
                    "score_reason": score_info.get("reason", "")
                })
            else:
                logger.warning(f"[{expert_id}] No score found for post {post_id}")
                # Include with 0.0 score if not found
                scored_posts.append({
                    "telegram_message_id": post_id,
                    "relevance": "MEDIUM",
                    "reason": post_data.get("reason", ""),
                    "content": post_data.get("content", ""),
                    "author": post_data.get("author", ""),
                    "created_at": post_data.get("created_at", ""),
                    "score": 0.0,
                    "score_reason": "Not scored by LLM"
                })

        # Filter by score >= 0.7
        above_threshold = [p for p in scored_posts if p.get("score", 0) >= self.score_threshold]

        # Sort by score (highest first) and limit to MAX_SELECTED_POSTS
        selected_posts = sorted(
            above_threshold,
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:self.max_selected_posts]

        logger.info(
            f"[{expert_id}] Medium Scoring Phase END: "
            f"{len(medium_posts)} → {len(above_threshold)} posts (score >= {self.score_threshold}) "
            f"→ {len(selected_posts)} posts selected (max {self.max_selected_posts})"
        )

        if progress_callback:
            await progress_callback({
                "phase": "medium_scoring",
                "status": "completed",
                "message": f"Selected {len(selected_posts)} MEDIUM posts from {len(medium_posts)} (score >= {self.score_threshold})",
                "selected_count": len(selected_posts),
                "above_threshold": len(above_threshold),
                "total_medium": len(medium_posts),
                "expert_id": expert_id
            })

        return selected_posts