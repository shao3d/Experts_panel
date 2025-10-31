"""Map service for processing posts in parallel chunks."""

import asyncio
import json
import os
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import logging
from pathlib import Path
from string import Template

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from json_repair import repair_json

from ..models.post import Post
from .openrouter_adapter import create_openrouter_client, convert_model_name
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language
from ..utils.error_handler import error_handler

logger = logging.getLogger(__name__)


class MapService:
    """Service for the Map phase of the Map-Resolve-Reduce pipeline.

    Processes posts in parallel chunks, scoring relevance for each post
    relative to the user's query using Gemini 2.0 Flash.
    """

    DEFAULT_CHUNK_SIZE = 40
    DEFAULT_MODEL = os.getenv("MODEL_ANALYSIS", "qwen-2.5-72b")  # Configurable via MODEL_ANALYSIS environment variable

    def __init__(
        self,
        api_key: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        model: str = DEFAULT_MODEL,
        max_parallel: int = None
    ):
        """Initialize MapService.

        Args:
            api_key: OpenAI API key
            chunk_size: Number of posts per chunk (default 30)
            model: OpenAI model to use (default gpt-4o-mini)
            max_parallel: Maximum parallel API calls (None = all chunks in parallel)
        """
        self.client = create_openrouter_client(api_key=api_key)
        self.chunk_size = chunk_size
        self.model = convert_model_name(model)
        self.max_parallel = max_parallel
        self._prompt_template = self._load_prompt_template()

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, ValueError)),
        reraise=True
    )
    async def _process_chunk(
        self,
        chunk: List[Post],
        query: str,
        chunk_index: int,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Process a single chunk of posts.

        Args:
            chunk: List of posts in this chunk
            query: User's query
            chunk_index: Index of this chunk (for progress tracking)
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

            # Call OpenAI API - use simple JSON mode for Qwen compatibility
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": enhanced_system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}  # Simple JSON mode for Qwen
            )

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
        # If max_parallel is None, use the number of chunks (all in parallel)
        parallel_limit = self.max_parallel if self.max_parallel is not None else total_chunks
        semaphore = asyncio.Semaphore(parallel_limit)

        async def process_with_semaphore(chunk, index):
            async with semaphore:
                return await self._process_chunk(chunk, query, index, progress_callback)

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
                self._process_chunk(chunk, query, index, progress_callback)
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