"""Translation service for translating posts to English."""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from string import Template

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from .openrouter_adapter import create_openrouter_client, convert_model_name
from ..utils.language_utils import detect_query_language

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating posts to English for English queries."""

    def __init__(
        self,
        api_key: str,
        model: str
    ):
        """Initialize TranslationService.

        Args:
            api_key: OpenAI API key
            model: Model to use (configured via MODEL_ANALYSIS environment variable)
        """
        # Always use OpenRouter for translation (Qwen models not supported by Google AI Studio)
        # This provides reliable translation service with configurable model support
        self.client = create_openrouter_client(api_key=api_key)
        self.model = convert_model_name(model)

        logger.info(f"TranslationService initialized with OpenRouter, model: {self.model}")
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template:
        """Load the translation prompt template."""
        try:
            # Use relative path from current file location
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "translation_prompt.txt"

            with open(prompt_path, "r", encoding="utf-8") as f:
                return Template(f.read())
        except FileNotFoundError:
            logger.error(f"Translation prompt template not found at {prompt_path}")
            # Fallback to simple inline prompt
            return Template("Translate the following Russian Telegram post to natural English:\n\n${post_text}\n\nKeep all links [text](url) unchanged and preserve formatting.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, ValueError)),
        reraise=True
    )
    async def translate_single_post(self, post_text: str, author_name: str = "Unknown") -> str:
        """Translate a single post from Russian to English.

        Args:
            post_text: The post text to translate
            author_name: The author name for context

        Returns:
            Translated text in English
        """
        try:
            if not post_text or not post_text.strip():
                return post_text

            # Create the translation prompt
            prompt = self._prompt_template.substitute(
                post_text=post_text,
                author_name=author_name
            )

            # Prepare system message
            system_message = "You are a helpful translator. Translate Russian Telegram posts to natural English while preserving all links and formatting."

            # Call LLM API using OpenRouter client
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2  # Low temperature for consistent translation
            )

            # Get translated text
            translated_text = response.choices[0].message.content.strip()

            if not translated_text:
                logger.warning("Empty translation response, returning original text")
                return post_text

            logger.debug(f"Translated post from {author_name}: {post_text[:50]}... -> {translated_text[:50]}...")
            return translated_text

        except Exception as e:
            logger.error(f"Error translating post: {str(e)}")
            # Return original text if translation fails
            return post_text

    async def translate_posts_batch(
        self,
        posts: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Translate multiple posts in parallel.

        Args:
            posts: List of post dictionaries with 'message_text' and 'author_name' keys
            progress_callback: Optional callback for progress updates

        Returns:
            List of posts with translated 'message_text'
        """
        if not posts:
            return posts

        logger.info(f"Translating {len(posts)} posts to English")

        if progress_callback:
            await progress_callback({
                "status": "starting_translation",
                "message": f"Starting translation of {len(posts)} posts"
            })

        # Create translation tasks
        async def translate_post_with_index(post_data, index):
            translated_text = await self.translate_single_post(
                post_data.get("message_text", ""),
                post_data.get("author_name", "Unknown")
            )

            # Create new post dict with translated text
            translated_post = post_data.copy()
            translated_post["message_text"] = translated_text
            translated_post["original_message_text"] = post_data.get("message_text", "")

            if progress_callback:
                await progress_callback({
                    "status": "translating",
                    "post_index": index,
                    "total_posts": len(posts),
                    "message": f"Translated post {index + 1}/{len(posts)}"
                })

            return translated_post

        # Process all posts in parallel (with reasonable concurrency)
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent translations

        async def translate_with_semaphore(post_data, index):
            async with semaphore:
                return await translate_post_with_index(post_data, index)

        # Create tasks for all posts
        tasks = [
            translate_with_semaphore(post, i)
            for i, post in enumerate(posts)
        ]

        # Wait for all translations to complete
        translated_posts = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any translation errors
        successful_posts = []
        for i, result in enumerate(translated_posts):
            if isinstance(result, Exception):
                logger.error(f"Translation failed for post {i}: {result}")
                # Keep original post if translation failed
                successful_posts.append(posts[i])
            else:
                successful_posts.append(result)

        if progress_callback:
            await progress_callback({
                "status": "translation_completed",
                "message": f"Completed translation of {len(successful_posts)} posts"
            })

        logger.info(f"Translation completed: {len(successful_posts)}/{len(posts)} posts processed")
        return successful_posts

    def should_translate(self, query: Optional[str]) -> bool:
        """Check if posts should be translated based on query language.

        Args:
            query: The user's query

        Returns:
            True if translation is needed (English query), False otherwise
        """
        if not query or not query.strip():
            return False

        detected_language = detect_query_language(query)
        return detected_language == "English"