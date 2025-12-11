"""Translation service for translating posts to English."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from string import Template

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError
from ..utils.language_utils import detect_query_language

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating posts to English using Google AI Studio."""

    def __init__(
        self,
        model: str = "gemini-2.0-flash"
    ):
        """Initialize TranslationService.

        Args:
            model: Model to use (default Gemini via Google)
        """
        # Initialize Google Client
        self.google_client = None
        try:
            self.google_client = create_google_ai_studio_client()
            if self.google_client:
                logger.info("TranslationService: Google AI Studio client initialized.")
        except Exception as e:
            logger.warning(f"TranslationService: Could not initialize Google AI Studio client: {e}")

        self.primary_model = model

        logger.info(f"TranslationService Config: Model={self.primary_model}")
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> Template:
        """Load the translation prompt template."""
        try:
            prompt_dir = Path(__file__).parent.parent.parent / "prompts"
            prompt_path = prompt_dir / "translation_prompt.txt"

            with open(prompt_path, "r", encoding="utf-8") as f:
                return Template(f.read())
        except FileNotFoundError:
            logger.error(f"Translation prompt template not found at {prompt_path}")
            return Template("Translate the following Russian Telegram post to natural English:\n\n${post_text}\n\nKeep all links [text](url) unchanged and preserve formatting.")

    async def _call_llm(self, model_name: str, messages: List[Dict[str, str]]):
        """Call Google AI Studio."""
        if self.google_client:
            # Google client handles key rotation automatically
            return await self.google_client.chat_completions_create(
                model=model_name,
                messages=messages,
                temperature=0.2
            )
        raise ValueError("Google Client not initialized")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, ValueError)),
        reraise=True
    )
    async def translate_single_post(self, post_text: str, author_name: str = "Unknown") -> str:
        """Translate a single post from Russian to English."""
        try:
            if not post_text or not post_text.strip():
                return post_text

            # Create prompt
            prompt = self._prompt_template.substitute(
                post_text=post_text,
                author_name=author_name
            )

            messages = [
                {"role": "system", "content": "You are a helpful translator. Translate Russian Telegram posts to natural English while preserving all links and formatting."},
                {"role": "user", "content": prompt}
            ]

            response = None

            # Direct call to Google model
            response = await self._call_llm(self.primary_model, messages)

            # Get translated text
            translated_text = response.choices[0].message.content.strip()

            if not translated_text:
                logger.warning("Empty translation response, returning original text")
                return post_text

            logger.debug(f"Translated post from {author_name} using Hybrid service")
            return translated_text

        except Exception as e:
            logger.error(f"Error translating post: {str(e)}")
            return post_text

    async def translate_posts_batch(
        self,
        posts: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Translate multiple posts in parallel."""
        if not posts:
            return posts

        logger.info(f"Translating {len(posts)} posts to English")

        if progress_callback:
            await progress_callback({
                "status": "starting_translation",
                "message": f"Starting translation of {len(posts)} posts"
            })

        async def translate_post_with_index(post_data, index):
            translated_text = await self.translate_single_post(
                post_data.get("message_text", ""),
                post_data.get("author_name", "Unknown")
            )
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

        # Limit concurrency for translation (safe for Google)
        semaphore = asyncio.Semaphore(5)

        async def translate_with_semaphore(post_data, index):
            async with semaphore:
                return await translate_post_with_index(post_data, index)

        tasks = [translate_with_semaphore(post, i) for i, post in enumerate(posts)]
        translated_posts = await asyncio.gather(*tasks, return_exceptions=True)

        successful_posts = []
        for i, result in enumerate(translated_posts):
            if isinstance(result, Exception):
                logger.error(f"Translation failed for post {i}: {result}")
                successful_posts.append(posts[i])
            else:
                successful_posts.append(result)

        if progress_callback:
            await progress_callback({
                "status": "translation_completed",
                "message": f"Completed translation of {len(successful_posts)} posts"
            })

        return successful_posts

    def should_translate(self, query: Optional[str]) -> bool:
        """Check if posts should be translated based on query language."""
        if not query or not query.strip():
            return False
        detected_language = detect_query_language(query)
        return detected_language == "English"