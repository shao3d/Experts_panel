"""Embedding service backed by OpenRouter's embeddings endpoint."""

import asyncio
import logging
import random
from typing import List, Optional

import requests

from .. import config

logger = logging.getLogger(__name__)
_DEFAULT_TIMEOUT_SECONDS = 60
_BATCH_CONCURRENCY = 8
_MAX_RETRY_ATTEMPTS = 4
_BASE_BACKOFF_SECONDS = 2.0
_MAX_BACKOFF_SECONDS = 12.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 529}


class RetryableEmbeddingError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, retry_after: Optional[float] = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class EmbeddingService:
    """Generate compatible 768-dimension Gemini embeddings through OpenRouter."""

    def __init__(self):
        self.model = config.MODEL_EMBEDDING
        self.dimensions = config.EMBEDDING_DIMENSIONS
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        if not self.api_key:
            logger.error("EmbeddingService: OpenRouter API key is not configured")
        logger.info("EmbeddingService initialized: %s @ %sd via OpenRouter", self.model, self.dimensions)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _input_type(task_type: str) -> str:
        return {
            "RETRIEVAL_DOCUMENT": "search_document",
            "RETRIEVAL_QUERY": "search_query",
        }.get(task_type, task_type.lower())

    def _parse_retry_after(self, value: Optional[str]) -> Optional[float]:
        try:
            return max(0.0, min(float(value or ""), _MAX_BACKOFF_SECONDS))
        except ValueError:
            return None

    def _parse_embedding_response(self, payload: object) -> List[float]:
        """Validate OpenRouter's OpenAI-compatible embedding response at its boundary."""
        if not isinstance(payload, dict):
            raise RuntimeError("OpenRouter embeddings returned a non-object JSON response")

        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise RuntimeError("OpenRouter embeddings response did not contain data[0]")

        embedding = data[0].get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError("OpenRouter embeddings response did not contain a numeric embedding")
        if len(embedding) != self.dimensions:
            raise RuntimeError(
                "OpenRouter embedding dimensions mismatch: "
                f"expected {self.dimensions}, got {len(embedding)}"
            )
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in embedding):
            raise RuntimeError("OpenRouter embeddings response contained a non-numeric vector value")

        return [float(value) for value in embedding]

    def _embed(self, text: str, task_type: str) -> List[float]:
        if not self.api_key:
            raise RuntimeError("OpenRouter API key is not configured")
        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "input": text,
                    "dimensions": self.dimensions,
                    "encoding_format": "float",
                    "input_type": self._input_type(task_type),
                    "provider": {"require_parameters": True},
                },
                timeout=_DEFAULT_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise RetryableEmbeddingError(f"Network error while calling OpenRouter embeddings: {exc}") from exc
        if response.ok:
            try:
                return self._parse_embedding_response(response.json())
            except ValueError as exc:
                raise RuntimeError("OpenRouter embeddings returned invalid JSON") from exc
        try:
            message = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            message = response.text
        if response.status_code in _RETRYABLE_STATUS_CODES:
            raise RetryableEmbeddingError(
                f"Error code: {response.status_code} - {message}", response.status_code,
                self._parse_retry_after(response.headers.get("Retry-After")),
            )
        raise RuntimeError(f"Error code: {response.status_code} - {message}")

    async def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
            try:
                return await asyncio.to_thread(self._embed, text, task_type)
            except RetryableEmbeddingError as exc:
                if attempt >= _MAX_RETRY_ATTEMPTS:
                    raise
                delay = exc.retry_after or min(_MAX_BACKOFF_SECONDS, _BASE_BACKOFF_SECONDS * 2 ** (attempt - 1)) + random.uniform(0, 0.75)
                logger.warning("OpenRouter embedding transient error; retrying in %.1fs (%s/%s)", delay, attempt, _MAX_RETRY_ATTEMPTS)
                await asyncio.sleep(delay)

    async def embed_query(self, query: str) -> List[float]:
        return await self.embed_text(query, task_type="RETRIEVAL_QUERY")

    async def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        if not texts:
            return []
        semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
        async def one(text: str) -> List[float]:
            async with semaphore:
                return await self.embed_text(text, task_type)
        return await asyncio.gather(*(one(text) for text in texts))


_embedding_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingService()
    return _embedding_instance
