"""Map service for processing posts in parallel chunks."""

import asyncio
import json
import os
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import logging
from pathlib import Path
from string import Template

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from json_repair import repair_json

from ..models.post import Post
from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language
from ..utils.error_handler import error_handler
from ..config import MAP_MAX_PARALLEL

logger = logging.getLogger(__name__)


class MapService:
    """Service for the Map phase of the Map-Resolve-Reduce pipeline.

    Processes posts in parallel chunks, scoring relevance for each post
    relative to the user's query using configurable models.
    """

    DEFAULT_CHUNK_SIZE = 100

    def __init__(
        self,
        model: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_parallel: int = None
    ):
        """Initialize MapService.

        Args:
            model: Model to use for the Map phase (Gemini).
            chunk_size: Number of posts per chunk
            max_parallel: Maximum parallel API calls (None = all chunks in parallel)
        """
        # Initialize Google client
        self.google_client = None
        try:
            self.google_client = create_google_ai_studio_client()
            if self.google_client:
                logger.info("MapService: Google AI Studio client initialized.")
        except Exception as e:
            logger.warning(f"MapService: Could not initialize Google AI Studio client: {e}")

        self.chunk_size = chunk_size
        self.primary_model = model
        self.max_parallel = max_parallel
        logger.info(f"MapService model: {self.primary_model}")
        self._prompt_template = self._load_prompt_template()
        self.minute_start_time: Optional[float] = None
        self.requests_in_current_minute: int = 0
        self.lock = asyncio.Lock()

        # Rate limiting metrics
        self.rate_limit_hits = 0
        self.total_requests = 0

    def _reset_rate_limit_state(self):
        """Reset rate limiting state for new query session."""
        self.minute_start_time = None
        self.requests_in_current_minute = 0

    def _load_prompt_template(self) -> Template:
        """Load the map phase prompt template."""
        try:
            # Use relative path from current file location
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "map_prompt.txt"

            with open(prompt_path, "r", encoding="utf-8") as f:
                return Template(f.read())
        except FileNotFoundError:
            logger.error(f"Map prompt template not found at {prompt_path}")
            raise

    def _chunk_posts(self, posts: List[Post]) -> List[List[Post]]:
        """Split posts into chunks of specified size.

        Args:
            posts: List of Post objects to chunk

        Returns:
            List of post chunks
        """
        chunks = []
        for i in range(0, len(posts), self.chunk_size):
            chunks.append(posts[i:i + self.chunk_size])
        return chunks

    def _get_russian_month(self, date: datetime) -> str:
        """Get Russian month name from date.

        Args:
            date: Datetime object

        Returns:
            Russian month name with year
        """
        month_names = {
            1: "январь", 2: "февраль", 3: "март",
            4: "апрель", 5: "май", 6: "июнь",
            7: "июль", 8: "август", 9: "сентябрь",
            10: "октябрь", 11: "ноябрь", 12: "декабрь"
        }
        month_name = month_names.get(date.month, "unknown")
        return f"{month_name} {date.year}"

    def _sanitize_text(self, text: str) -> str:
        """Remove invalid escape sequences from text.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text safe for JSON
        """
        import re
        if not text:
            return text
        # Remove invalid escape sequences, keep only valid JSON escapes
        return re.sub(r'\\(?![ntr"\\/])', '', text)

    def _format_posts_for_prompt(self, posts: List[Post]) -> str:
        """Format posts for inclusion in the prompt.

        Args:
            posts: List of Post objects

        Returns:
            Formatted string representation of posts
        """
        formatted_posts = []
        for post in posts:

            post_data = {
                "telegram_message_id": post.telegram_message_id,
                "date": post.created_at.strftime("%Y-%m-%d %H:%M"),
                "month_year": self._get_russian_month(post.created_at),
                "content": self._sanitize_text(post.message_text) or "[Media only]",
                "author": self._sanitize_text(post.author_name) or "Unknown"
            }


            formatted_posts.append(post_data)

        return json.dumps(formatted_posts, ensure_ascii=False, indent=2)

    async def _call_llm(self, model_name: str, prompt: str, system_message: str):
        """Calls the Google AI Studio client."""
        if self.google_client:
            logger.info(f"Using Google AI Studio client for model: {model_name}")
            return await self.google_client.chat_completions_create(
                model=model_name,
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
        raise ValueError("Google Client not initialized")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=90),
        retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
        reraise=True
    )
    async def _process_chunk(
        self,
        chunk: List[Post],
        query: str,
        chunk_index: int,
        expert_id: str = "unknown",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process a single chunk of posts with a primary/fallback model strategy.

        Args:
            chunk: List of posts in this chunk
            query: User's query
            chunk_index: Index of this chunk (for progress tracking)
            expert_id: Expert identifier for logging
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with relevant_posts and chunk_summary
        """
        try:
            if progress_callback:
                await progress_callback({
                    "phase": "map",
                    "status": "processing",
                    "message": f"Processing chunk {chunk_index + 1}",
                    "chunk_index": chunk_index,
                    "total_chunks": None  # Will be set by parent
                })

            # Stopwatch logic for rate limiting, protected by a lock to handle concurrency
            async with self.lock:
                current_time = time.time()

                # If the stopwatch hasn't started for this batch, start it.
                if self.minute_start_time is None:
                    self.minute_start_time = current_time
                    self.requests_in_current_minute = 0

                # If 60 or more seconds have passed, reset the stopwatch.
                elapsed = current_time - self.minute_start_time
                if elapsed >= 60:
                    self.minute_start_time = current_time
                    self.requests_in_current_minute = 0

                self.requests_in_current_minute += 1
            self.total_requests += 1

            # Format the prompt
            posts_formatted = self._format_posts_for_prompt(chunk)

            # Create base prompt
            base_prompt = self._prompt_template.substitute(
                query=query,
                posts=posts_formatted
            )

            # Apply language instruction based on query language
            prompt = prepare_prompt_with_language_instruction(base_prompt, query)



            # Prepare enhanced system message with language instruction
            enhanced_system = prepare_system_message_with_language(
                "You are a helpful assistant that analyzes Telegram posts.",
                query
            )

            response = None
            try:
                # Attempt to call model
                logger.info(f"Chunk {chunk_index}: Attempting model '{self.primary_model}'")
                response = await self._call_llm(self.primary_model, prompt, enhanced_system)
                logger.info(f"Chunk {chunk_index}: Model '{self.primary_model}' successful.")

            except (GoogleAIStudioError, httpx.HTTPStatusError) as e:
                error_str = str(e).lower()
                is_rate_limit_error = (
                    (isinstance(e, GoogleAIStudioError) and e.is_rate_limit) or
                    '429' in error_str or 'rate limit' in error_str or 'quota' in error_str
                )

                if is_rate_limit_error:
                    # Even with rotation, if we hit a global limit, wait and retry once
                    self.rate_limit_hits += 1
                    wait_time = 65.0  # Simple, robust wait time to ensure the next minute window
                    logger.warning(f"Chunk {chunk_index}: Rate limit/Exhaustion hit. Waiting {wait_time}s before retry.")

                    # The sleep happens outside the lock, so other tasks are not blocked
                    await asyncio.sleep(wait_time)

                    # After waiting, briefly lock to reset the shared stopwatch state.
                    # This is a very short operation, avoiding contention.
                    async with self.lock:
                        self.minute_start_time = time.time()  # Set to current time, not None
                        self.requests_in_current_minute = 0

                    # Retry the same call once. If this also fails, it will propagate up.
                    try:
                        response = await self._call_llm(self.primary_model, prompt, enhanced_system)
                        logger.info(f"Chunk {chunk_index}: Retry after rate limit wait successful.")
                    except Exception as retry_e:
                        logger.error(f"Chunk {chunk_index}: Retry after wait FAILED. Giving up on this chunk. Error: {retry_e}")
                        raise retry_e # Re-raise to mark the chunk as failed
                else:
                    # Not a rate limit error, re-raise to be handled by tenacity
                    raise e

            if response is None:
                raise ValueError("Primary model failed to produce a response after retry.")

            # Parse response (strict mode guarantees valid JSON)
            raw_content = response.choices[0].message.content

            # Validate non-empty response
            if not raw_content or not raw_content.strip():
                logger.error(f"Empty response from API for chunk {chunk_index}")
                raise ValueError(f"Empty API response for chunk {chunk_index}")

            result = json.loads(raw_content)


            # Add chunk metadata
            result["chunk_index"] = chunk_index
            result["posts_processed"] = len(chunk)

            if progress_callback:
                await progress_callback({
                    "phase": "map",
                    "status": "progress",
                    "message": f"Chunk {chunk_index + 1} completed",
                    "chunk_index": chunk_index,
                    "relevant_found": len(result.get("relevant_posts", []))
                })

            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in chunk {chunk_index}: {str(e)}")
            # Log response preview for debugging (capture raw_content from outer scope)
            try:
                response_preview = raw_content[:500] if 'raw_content' in locals() else "N/A"
                logger.error(f"Response preview (first 500 chars): {response_preview}")
            except Exception:
                pass
            if progress_callback:
                await progress_callback({
                    "phase": "map",
                    "chunk": chunk_index,
                    "status": "error",
                    "message": f"JSON decode error in chunk {chunk_index + 1}"
                })
            raise
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_index}: {str(e)}")

            # Process error through error handler for user-friendly messaging
            error_info = error_handler.process_api_error(
                e,
                context={
                    "phase": "map",
                    "chunk": chunk_index,
                    "expert_id": expert_id
                }
            )

            if progress_callback:
                await progress_callback({
                    "phase": "map",
                    "chunk": chunk_index,
                    "status": "error",
                    "message": f"Error in chunk {chunk_index + 1}: {str(e)}",
                    "error_info": error_info  # Add detailed error information
                })
            raise

    async def process(
        self,
        posts: List[Post],
        query: str,
        expert_id: str = "unknown",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process all posts in parallel chunks.

        Args:
            posts: List of all Post objects to process
            query: User's query
            expert_id: Expert identifier for logging
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with aggregated results from all chunks
        """
        import time
        phase_start_time = time.time()

        # Reset rate limiting state for new query session
        self._reset_rate_limit_state()

        if not posts:
            return {
                "relevant_posts": [],
                "total_processed": 0,
                "chunks_processed": 0,
                "summary": "No posts to process"
            }

        # Split into chunks
        chunks = self._chunk_posts(posts)
        total_chunks = len(chunks)

        logger.info(f"[{expert_id}] Processing {len(posts)} posts in {total_chunks} chunks of {self.chunk_size}")

        if progress_callback:
            await progress_callback({
                "phase": "map",
                "status": "starting",
                "message": f"Starting Map phase: {len(posts)} posts in {total_chunks} chunks",
                "total_chunks": total_chunks,
                "chunk_index": 0
            })

        # Process chunks in parallel with dynamic concurrency limit
        # If max_parallel is None, use the safe limit from config to protect Google Keys
        if self.max_parallel is not None:
            parallel_limit = self.max_parallel
        else:
            # Use configured safe limit (e.g. 8 for 5 keys)
            # But don't use more threads than we have chunks
            parallel_limit = min(MAP_MAX_PARALLEL, total_chunks)

        logger.info(f"[{expert_id}] Map Phase concurrency limit: {parallel_limit} (Total chunks: {total_chunks})")
        semaphore = asyncio.Semaphore(parallel_limit)

        async def process_with_semaphore(chunk, index):
            async with semaphore:
                return await self._process_chunk(chunk, query, index, expert_id, progress_callback)

        # Create tasks for all chunks
        tasks = [
            process_with_semaphore(chunk, i)
            for i, chunk in enumerate(chunks)
        ]

        # Wait for all chunks to complete
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results and identify failed chunks for retry
        all_relevant_posts = []
        chunks_with_errors = []
        failed_chunks = []

        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                logger.error(f"Chunk {i} failed: {result}")
                chunks_with_errors.append(i)
                # Store failed chunk info for retry
                failed_chunks.append((chunks[i], i))
            else:
                all_relevant_posts.extend(result.get("relevant_posts", []))

        # Global retry mechanism for failed chunks
        retry_attempts = 0
        max_global_retries = 1

        while failed_chunks and retry_attempts < max_global_retries:
            retry_attempts += 1
            logger.info(f"[{expert_id}] Global retry attempt {retry_attempts} for {len(failed_chunks)} failed chunks")

            if progress_callback:
                await progress_callback({
                    "phase": "map",
                    "status": "retrying",
                    "message": f"Global retry {retry_attempts} for {len(failed_chunks)} failed chunks"
                })

            # Retry failed chunks
            retry_tasks = [
                self._process_chunk(chunk, query, index, expert_id, progress_callback)
                for chunk, index in failed_chunks
            ]

            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

            # Process retry results
            new_failed_chunks = []

            for (chunk, original_index), result in zip(failed_chunks, retry_results):
                if isinstance(result, Exception):
                    logger.error(f"[{expert_id}] Chunk {original_index} failed on retry {retry_attempts}: {result}")
                    new_failed_chunks.append((chunk, original_index))
                else:
                    logger.info(f"[{expert_id}] Chunk {original_index} recovered on retry {retry_attempts}")
                    all_relevant_posts.extend(result.get("relevant_posts", []))
                    # Remove from error list since it recovered
                    chunks_with_errors.remove(original_index)

            failed_chunks = new_failed_chunks

        if failed_chunks:
            logger.warning(f"[{expert_id}] {len(failed_chunks)} chunks still failed after {max_global_retries} global retries")
            for chunk, index in failed_chunks:
                logger.error(f"[{expert_id}] Chunk {index} permanently failed after all retries")

        # Sort by relevance (HIGH > MEDIUM > LOW)
        relevance_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        all_relevant_posts.sort(
            key=lambda x: (relevance_order.get(x.get("relevance", "LOW"), 3), x.get("telegram_message_id", 0))
        )

        # Create final summary
        high_count = sum(1 for p in all_relevant_posts if p.get("relevance") == "HIGH")
        medium_count = sum(1 for p in all_relevant_posts if p.get("relevance") == "MEDIUM")
        low_count = sum(1 for p in all_relevant_posts if p.get("relevance") == "LOW")

        summary = (
            f"Processed {len(posts)} posts in {total_chunks} chunks. "
            f"Found {len(all_relevant_posts)} relevant posts: "
            f"{high_count} HIGH, {medium_count} MEDIUM, {low_count} LOW relevance."
        )

        if chunks_with_errors:
            summary += f" {len(chunks_with_errors)} chunks had errors."

        # Log phase completion with timing
        duration_ms = int((time.time() - phase_start_time) * 1000)
        logger.info(
            f"[{expert_id}] Map Phase END: {duration_ms}ms, "
            f"found {len(all_relevant_posts)} posts "
            f"({high_count} HIGH, {medium_count} MEDIUM, {low_count} LOW)"
        )

        if progress_callback:
            await progress_callback({
                "phase": "map",
                "status": "completed",
                "message": "Map phase completed",
                "summary": summary
            })

        return {
            "relevant_posts": all_relevant_posts,
            "total_processed": len(posts),
            "chunks_processed": total_chunks - len(chunks_with_errors),
            "chunks_with_errors": chunks_with_errors,
            "summary": summary,
            "statistics": {
                "high_relevance": high_count,
                "medium_relevance": medium_count,
                "low_relevance": low_count
            }
        }