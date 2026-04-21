"""Embedding service backed by Vertex AI text embeddings."""

import asyncio
import logging
from typing import List

import requests

from .. import config
from .vertex_ai_auth import get_vertex_ai_auth_manager

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 60
_BATCH_CONCURRENCY = 8


class EmbeddingService:
    """Service for generating text embeddings via Vertex AI."""

    def __init__(self):
        self.model = config.MODEL_EMBEDDING
        self.dimensions = config.EMBEDDING_DIMENSIONS
        self._auth_manager = get_vertex_ai_auth_manager()

        if not self._auth_manager.is_configured():
            logger.error("❌ EmbeddingService: Vertex AI auth is not configured")

        logger.info(
            "✅ EmbeddingService initialized: %s @ %sd via Vertex AI",
            self.model,
            self.dimensions,
        )

    def _build_predict_url(self) -> str:
        project_id = self._auth_manager.project_id
        location = self._auth_manager.location
        return (
            f"https://{location}-aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/{location}/publishers/google/models/{self.model}:predict"
        )

    def _predict_embedding(
        self, url: str, token: str, text: str, task_type: str
    ) -> List[float]:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "instances": [{"content": text}],
                "parameters": {
                    "autoTruncate": True,
                    "taskType": task_type,
                    "outputDimensionality": self.dimensions,
                },
            },
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )

        if response.ok:
            payload = response.json()
            return payload["predictions"][0]["embeddings"]["values"]

        try:
            error_message = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            error_message = response.text

        raise RuntimeError(f"Error code: {response.status_code} - {error_message}")

    async def embed_text(
        self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[float]:
        """Embed one text using Vertex AI predict endpoint."""

        if task_type not in {"RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"}:
            logger.warning("Unsupported task_type=%s, passing through to Vertex", task_type)

        try:
            token = await self._auth_manager.get_access_token()
            url = self._build_predict_url()
            return await asyncio.to_thread(
                self._predict_embedding,
                url,
                token,
                text,
                task_type,
            )
        except Exception as exc:
            logger.error("❌ Embedding failed for text: %s", exc)
            raise

    async def embed_query(self, query: str) -> List[float]:
        return await self.embed_text(query, task_type="RETRIEVAL_QUERY")

    async def embed_batch(
        self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[List[float]]:
        """Embed multiple texts.

        Vertex's gemini-embedding-001 accepts one input text per request, so
        batching here means bounded concurrency rather than one network call.
        """

        if not texts:
            return []

        semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

        async def _embed_one(text: str) -> List[float]:
            async with semaphore:
                return await self.embed_text(text, task_type=task_type)

        return await asyncio.gather(*(_embed_one(text) for text in texts))


_embedding_instance = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingService()
    return _embedding_instance
