"""Translation service for translating posts and answers."""

import asyncio
import hashlib
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from string import Template
from collections import OrderedDict

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from .vertex_llm_client import get_vertex_llm_client

logger = logging.getLogger(__name__)

# Module-level singleton: keeps the in-memory LRU cache warm across requests
# and shares one LLM client. Instances created ad-hoc (e.g. per HTTP request)
# defeated the cache entirely, re-translating the same posts on every view.
_shared_instance: Optional["TranslationService"] = None


def get_translation_service() -> "TranslationService":
    """Return the shared TranslationService instance."""
    global _shared_instance
    if _shared_instance is None:
        _shared_instance = TranslationService()
    return _shared_instance


class TranslationService:
    """Service for translating posts to English through OpenRouter."""

    def __init__(
        self,
        model: str = None
    ):
        """Initialize TranslationService.

        Args:
            model: Model to use (default Gemini via Vertex AI). Defaults to MODEL_ANALYSIS from config.
        """
        if model is None:
            from .. import config
            model = config.MODEL_ANALYSIS
        # Initialize the shared OpenRouter LLM client.
        self.llm_client = None
        try:
            self.llm_client = get_vertex_llm_client()
            if self.llm_client:
                logger.info("TranslationService: OpenRouter LLM client initialized.")
        except Exception as e:
            logger.warning(f"TranslationService: Could not initialize OpenRouter LLM client: {e}")

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

    @staticmethod
    def _make_persistent_key(text: str, source_lang: str, target_lang: str) -> str:
        """Build a stable cache key from normalized text and language pair."""
        normalized = " ".join(text.split())
        raw = f"{normalized}|{source_lang}->{target_lang}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _db_cache_get(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Look up a cached translation in the database (survives restarts)."""
        key = self._make_persistent_key(text, source_lang, target_lang)
        try:
            from ..models.base import SessionLocal
            from ..models.translation_cache import TranslationCache

            with SessionLocal() as db:
                row = (
                    db.query(TranslationCache)
                    .filter(TranslationCache.cache_key == key)
                    .first()
                )
                if row:
                    return row.translated_text
        except Exception as e:
            # Cache miss on infrastructure failure must never break translation.
            logger.debug(f"Translation DB cache read failed: {e}")
        return None

    def _db_cache_set(
        self, text: str, source_lang: str, target_lang: str, translated: str
    ) -> None:
        """Persist a translation to the database (idempotent per cache key)."""
        key = self._make_persistent_key(text, source_lang, target_lang)
        try:
            from ..models.base import SessionLocal
            from ..models.translation_cache import TranslationCache

            with SessionLocal() as db:
                exists = (
                    db.query(TranslationCache.cache_key)
                    .filter(TranslationCache.cache_key == key)
                    .first()
                )
                if not exists:
                    db.add(
                        TranslationCache(
                            cache_key=key,
                            source_lang=source_lang,
                            target_lang=target_lang,
                            translated_text=translated,
                            model=self.primary_model,
                        )
                    )
                    db.commit()
        except Exception as e:
            logger.debug(f"Translation DB cache write failed: {e}")

    async def _call_llm(self, model_name: str, messages: List[Dict[str, str]]):
        """Call the shared OpenRouter LLM client."""
        if self.llm_client:
            # The shared client handles auth and retry automatically.
            return await self.llm_client.chat_completions_create(
                model=model_name,
                messages=messages,
                temperature=0.2
            )
        raise ValueError("OpenRouter LLM client not initialized")

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

            # Persistent cache (survives restarts; posts are static content)
            persisted = self._db_cache_get(post_text, "Russian", "English")
            if persisted:
                self._add_to_cache(cache_key, persisted)
                return persisted

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

            # Direct call to the shared Vertex model
            response = await self._call_llm(self.primary_model, messages)

            # Get translated text
            translated_text = response.choices[0].message.content.strip()

            if not translated_text:
                logger.warning("Empty translation response, returning original text")
                return post_text

            logger.debug(f"Translated post from {author_name} using Gemini")

            # Update cache
            self._add_to_cache(cache_key, translated_text)
            self._db_cache_set(post_text, "Russian", "English", translated_text)

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

        # Persistent cache (survives restarts)
        persisted = self._db_cache_get(text, source_lang, target_lang)
        if persisted:
            self._add_to_cache(cache_key, persisted)
            return persisted

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional translator. Translate from {source_lang} to {target_lang}. "
                        "Preserve meaning, technical terms, and tone. "
                        "CRITICAL: keep every [post:ID] citation marker EXACTLY as is (do not translate or renumber IDs), "
                        "keep all markdown links [text](url) with their URLs unchanged, "
                        "and preserve markdown formatting (bold, italic, lists, code blocks). "
                        "Return only the translation, no explanations."
                    ),
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
                self._db_cache_set(text, source_lang, target_lang, translated)
                return translated
            else:
                logger.warning("Empty translation, returning original")
                return text

        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return text

    async def translate_texts_batch(
        self,
        texts: List[str],
        source_lang: str = "Russian",
        target_lang: str = "English",
        concurrency: int = 5,
    ) -> List[str]:
        """Translate multiple texts concurrently, preserving input order.

        Used for comment groups and comment lists where per-item LLM calls
        are needed but the total latency should stay bounded. Cached texts
        return instantly without an LLM call.
        """
        if not texts:
            return []

        semaphore = asyncio.Semaphore(concurrency)

        async def translate_one(text_item: str) -> str:
            async with semaphore:
                return await self.translate_text(text_item, source_lang, target_lang)

        results = await asyncio.gather(*[translate_one(t) for t in texts])
        return list(results)

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
