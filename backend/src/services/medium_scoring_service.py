"""Medium posts scoring service for hybrid reranking with Google Gemini and Fallback."""

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
from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language

logger = logging.getLogger(__name__)


class MediumScoringService:
    """Service for scoring MEDIUM relevance posts using Hybrid approach (Google -> OpenRouter).

    Implements hybrid approach: LLM scores all MEDIUM posts 0.0-1.0,
    code selects posts with score >= 0.7 (max 5 posts by highest score).
    """

    # Configurable via environment variables
    SCORE_THRESHOLD = float(os.getenv("MEDIUM_SCORE_THRESHOLD", "0.7"))
    MAX_SELECTED_POSTS = int(os.getenv("MEDIUM_MAX_SELECTED_POSTS", "5"))
    MAX_MEDIUM_POSTS = int(os.getenv("MEDIUM_MAX_POSTS", "50"))  # Memory limit

    def __init__(self, api_key: str, model: str, fallback_model: str = None):
        """Initialize MediumScoringService with Hybrid Logic.

        Args:
            api_key: OpenAI API key (for OpenRouter fallback)
            model: Primary model (usually Google Gemini)
            fallback_model: Fallback model (usually Qwen via OpenRouter)
        """
        # 1. Initialize Google Client (Primary)
        self.google_client = None
        try:
            self.google_client = create_google_ai_studio_client()
            if self.google_client:
                logger.info("MediumScoringService: Google AI Studio client initialized.")
        except Exception as e:
            logger.warning(f"MediumScoringService: Could not initialize Google AI Studio client: {e}")

        # 2. Initialize OpenRouter Client (Fallback)
        self.openrouter_client = create_openrouter_client(api_key=api_key)
        self.api_key_masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"

        # Configure models
        self.primary_model = model
        self.fallback_model = fallback_model or "qwen/qwen-2.5-72b-instruct"

        self.score_threshold = self.SCORE_THRESHOLD
        self.max_selected_posts = self.MAX_SELECTED_POSTS
        self.max_medium_posts = self.MAX_MEDIUM_POSTS
        self._prompt_template = self._load_prompt_template()

        logger.info(f"MediumScoringService Config: Primary={self.primary_model}, Fallback={self.fallback_model}")

    def _sanitize_text(self, text: str) -> str:
        """Remove invalid escape sequences from text."""
        if not text:
            return text
        # Remove invalid escape sequences, keep only valid JSON escapes
        return re.sub(r'\\(?![ntr"\\/])', '', text)

    def _parse_text_response(self, raw_content: str, medium_posts: List[Dict[str, Any]], expert_id: str) -> Dict[str, Any]:
        """Parse markdown text response from model and convert to JSON format.

        Note: Keeps existing parsing logic which is robust for Markdown outputs.
        """
        logger.info(f"[{expert_id}] Parsing markdown text response from model")
        sections = raw_content.split("=== POST")
        scored_posts = []

        for section in sections:
            if not section.strip(): continue

            post_data = {"telegram_message_id": None, "score": 0.0, "reason": ""}

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

    async def _call_llm(self, model_name: str, messages: List[Dict[str, str]], expert_id: str):
        """Unified method to call either Google or OpenRouter."""
        is_google_model = "gemini" in model_name or model_name.startswith("google/")

        # 1. Try Google
        if is_google_model and self.google_client:
            logger.info(f"[{expert_id}] Calling Google AI Studio ({model_name})...")
            # Google client handles key rotation automatically
            return await self.google_client.chat_completions_create(
                model=model_name,
                messages=messages,
                temperature=0.3,
                # Note: We DON'T force json_object here because the prompt expects Markdown text output
            )

        # 2. Try OpenRouter
        logger.info(f"[{expert_id}] Calling OpenRouter ({model_name})...")
        or_model = convert_model_name(model_name)
        return await self.openrouter_client.chat.completions.create(
            model=or_model,
            messages=messages,
            temperature=0.3
        )

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
        """Score MEDIUM posts using Primary (Google) with Fallback (OpenRouter)."""

        if progress_callback:
            await progress_callback({
                "phase": "medium_scoring",
                "status": "scoring",
                "message": f"Scoring {len(medium_posts)} MEDIUM posts (Hybrid Mode)",
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
        # Log the actual data being sent
        logger.info(f"[{expert_id}] Sending {len(medium_posts)} posts to Hybrid LLM")

        # Create base prompt
        base_prompt = self._prompt_template.substitute(
            query=query,
            high_posts=high_posts_context,
            medium_posts=medium_posts_text
        )

        # Apply language instruction
        prompt = prepare_prompt_with_language_instruction(base_prompt, query)
        enhanced_system = prepare_system_message_with_language(
            "You are analyzing MEDIUM-relevance posts to determine which ones should complement HIGH-relevance posts.",
            query
        )

        messages = [
            {"role": "system", "content": enhanced_system},
            {"role": "user", "content": prompt}
        ]

        response = None

        # --- HYBRID EXECUTION BLOCK ---
        try:
            # Attempt 1: Primary Model (Google)
            response = await self._call_llm(self.primary_model, messages, expert_id)

        except (GoogleAIStudioError, httpx.HTTPStatusError) as e:
            # Only log warning for primary failure, then try fallback
            logger.warning(f"[{expert_id}] Primary model {self.primary_model} failed: {e}. Switching to Fallback.")

            # Attempt 2: Fallback Model (OpenRouter)
            try:
                response = await self._call_llm(self.fallback_model, messages, expert_id)
            except Exception as fallback_e:
                logger.error(f"[{expert_id}] Fallback model {self.fallback_model} also failed: {fallback_e}")
                raise fallback_e

        except Exception as e:
            # Catch-all for other primary errors
            logger.error(f"[{expert_id}] Unexpected error with primary model: {e}. Switching to Fallback.")
            response = await self._call_llm(self.fallback_model, messages, expert_id)

        # Process Response
        raw_content = response.choices[0].message.content

        if not raw_content or not raw_content.strip():
            logger.error(f"[{expert_id}] Empty response from LLM for medium scoring")
            raise ValueError("Empty LLM response for medium scoring")

        result = self._parse_text_response(raw_content, medium_posts, expert_id)

        # Validate response structure
        if not isinstance(result, dict) or "scored_posts" not in result:
             raise ValueError("Invalid response structure from LLM")

        scored_count = len(result["scored_posts"])
        logger.info(f"[{expert_id}] LLM scored {scored_count}/{len(medium_posts)} posts")

        if progress_callback:
            await progress_callback({
                "phase": "medium_scoring",
                "status": "completed",
                "message": f"Scored {len(medium_posts)} MEDIUM posts",
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
        """Score MEDIUM posts and filter by threshold and limit."""
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

        try:
            scoring_result = await self._score_medium_posts(
                medium_posts=medium_posts,
                high_posts_context=high_posts_context,
                query=query,
                expert_id=expert_id,
                progress_callback=progress_callback
            )
        except Exception as e:
            logger.error(f"[{expert_id}] Medium scoring failed: {e}")
            if progress_callback:
                await progress_callback({
                    "phase": "medium_scoring",
                    "status": "error",
                    "message": f"Scoring failed, using fallback: {str(e)}"
                })
            return []

        # Process scored posts (Merge scores with original data)
        scored_posts_data = scoring_result.get("scored_posts", [])
        scored_posts = []

        for post_data in medium_posts:
            post_id = post_data["telegram_message_id"]

            # Find matching score
            score_info = next(
                (s for s in scored_posts_data if s.get("telegram_message_id") == post_id),
                None
            )

            if score_info:
                scored_posts.append({
                    **post_data, # Keep original content/author/date
                    "score": score_info.get("score", 0.0),
                    "score_reason": score_info.get("reason", "")
                })
            else:
                scored_posts.append({
                    **post_data,
                    "score": 0.0,
                    "score_reason": "Not scored by LLM"
                })

        # Filter by score >= Threshold
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
                "expert_id": expert_id
            })

        return selected_posts