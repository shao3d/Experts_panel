"""Boundary tests for OpenRouter response normalization and embeddings."""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.services.embedding_service import EmbeddingService
from src.services.vertex_llm_client import OpenRouterLLMError, _Response


def test_chat_response_accepts_textual_openai_compatible_content():
    response = _Response(
        {
            "choices": [{"message": {"content": "{\"status\": \"ok\"}"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        },
        "google/gemini-2.5-flash-lite",
    )

    assert response.choices[0].message.content == '{"status": "ok"}'
    assert response.usage.total_tokens == 5


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": ["not text"]}}]},
    ],
)
def test_chat_response_rejects_unusable_content(payload):
    with pytest.raises(OpenRouterLLMError) as exc_info:
        _Response(payload, "google/gemini-2.5-flash-lite")

    assert exc_info.value.error_type == "invalid_response"


def _embedding_service(dimensions: int = 3) -> EmbeddingService:
    service = object.__new__(EmbeddingService)
    service.dimensions = dimensions
    return service


def test_embedding_response_accepts_exact_numeric_vector():
    service = _embedding_service()

    result = service._parse_embedding_response(
        {"data": [{"embedding": [1, 2.5, -0.25]}]}
    )

    assert result == [1.0, 2.5, -0.25]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": [{}]},
        {"data": [{"embedding": [0.1, 0.2]}]},
        {"data": [{"embedding": [0.1, True, 0.2]}]},
        {"data": [{"embedding": [0.1, "bad", 0.2]}]},
    ],
)
def test_embedding_response_rejects_invalid_shape_or_values(payload):
    service = _embedding_service()

    with pytest.raises(RuntimeError):
        service._parse_embedding_response(payload)
