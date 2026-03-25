"""Embedding service for hybrid vector search.

Uses Gemini Embedding API for text-to-vector conversion.
Follows singleton pattern like GoogleAIClient.
"""

import logging
import asyncio
from typing import List

import google.generativeai as genai

from .. import config

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings via Gemini API."""

    def __init__(self):
        self.model = config.MODEL_EMBEDDING  # "gemini-embedding-exp-03-07"
        self.dimensions = config.EMBEDDING_DIMENSIONS  # 768 (MRL)
        logger.info(
            f"✅ EmbeddingService initialized: {self.model} @ {self.dimensions}d"
        )

    async def embed_text(
        self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[float]:
        """Embed single text. genai.embed_content is sync → wrap in to_thread.

        Args:
            text: Text to embed
            task_type: RETRIEVAL_DOCUMENT for posts, RETRIEVAL_QUERY for queries

        Returns:
            List of float values (768 dimensions)
        """
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=f"models/{self.model}",
                content=text,
                task_type=task_type,
                output_dimensionality=self.dimensions,
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"❌ Embedding failed for text: {e}")
            raise

    async def embed_query(self, query: str) -> List[float]:
        """Embed user query with RETRIEVAL_QUERY task_type.

        Args:
            query: User query string

        Returns:
            List of float values (768 dimensions)
        """
        return await self.embed_text(query, task_type="RETRIEVAL_QUERY")

    async def embed_batch(
        self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[List[float]]:
        """Embed batch via native genai.embed_content(content=list[str]).

        1 API call per batch instead of N. For 1300 posts:
        ~26 calls (batch 50) vs ~1300 calls (sequential).

        Args:
            texts: List of texts to embed
            task_type: RETRIEVAL_DOCUMENT for posts

        Returns:
            List of embeddings, each is List[float] (768 dimensions)
        """
        if not texts:
            return []

        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=f"models/{self.model}",
                content=texts,  # list[str] → native batch
                task_type=task_type,
                output_dimensionality=self.dimensions,
            )
            return result["embedding"]  # list[list[float]]
        except Exception as e:
            logger.error(f"❌ Batch embedding failed: {e}")
            raise


# Singleton instance
_embedding_instance = None


def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService instance."""
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingService()
    return _embedding_instance
