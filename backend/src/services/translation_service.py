"""Translation service for translating posts to English."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from string import Template
from collections import OrderedDict

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from .google_ai_studio_client import create_google_ai_studio_client, GoogleAIStudioError
from ..utils.language_utils import detect_query_language

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating posts to English using Google AI Studio."""

    def __init__(
        self,
        model: str = None
    ):
        """Initialize TranslationService.

        Args:
            model: Model to use (default Gemini via Google). Defaults to MODEL_ANALYSIS from config.
        """
        if model is None:
            from .. import config
            model = config.MODEL_ANALYSIS
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
        
        # Simple LRU Cache
        self._cache = OrderedDict()
        self._cache_max_size = 1000

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
            
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get item from cache and move to end (LRU)."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _add_to_cache(self, key: str, value: str):
        """Add item to cache, removing oldest if full."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

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
                
            # Check cache
            cache_key = f"post:{post_text}:{author_name}"
            cached = self._get_from_cache(cache_key)
            if cached:
                return cached

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

            logger.debug(f"Translated post from {author_name} using Gemini")
            
            # Update cache
            self._add_to_cache(cache_key, translated_text)
            
            return translated_text

        except Exception as e:
            logger.error(f"Error translating post: {str(e)}")
            return post_text

    async def translate_text(
        self,
        text: str,
        source_lang: str = "Russian",
        target_lang: str = "English"
    ) -> str:
        """Translate text from source language to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language name (e.g., "Russian", "English")
            target_lang: Target language name (e.g., "English", "Russian")
        
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        # If source and target are the same, return original
        if source_lang.lower() == target_lang.lower():
            return text
            
        # Check cache
        cache_key = f"text:{text}:{source_lang}:{target_lang}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": f"You are a translator. Translate from {source_lang} to {target_lang}. Preserve meaning and technical terms. Return only the translation, no explanations."
                },
                {
                    "role": "user",
                    "content": f"Translate this text from {source_lang} to {target_lang}:\n\n{text}"
                }
            ]
            
            response = await self._call_llm(self.primary_model, messages)
            translated = response.choices[0].message.content.strip()
            
            if translated:
                logger.debug(f"Translated text: {text[:50]}... -> {translated[:50]}...")
                self._add_to_cache(cache_key, translated)
                return translated
            else:
                logger.warning("Empty translation, returning original")
                return text
                
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return text

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