#!/usr/bin/env python3
"""Translation failure honesty: the service raises instead of silently
returning the original text, and the response model carries the outcome.

Covers the 2026-09 regression where an OpenRouter 402 was swallowed inside
translate_single_post, so an English query displayed Russian posts with a
"Successfully translated" log line.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.api.models import SimplifiedPostDetailResponse
from src.services.translation_service import TranslationService

POST_TEXT = "Харнес — это инфраструктура вокруг модели."


class _RaisingLLMClient:
    async def chat_completions_create(self, **kwargs):
        raise RuntimeError("Error code: 402 - Payment Required")


class _EmptyResponseLLMClient:
    class _Response:
        class choices:
            pass

    async def chat_completions_create(self, **kwargs):
        class _Msg:
            content = "   "

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


def _make_service(llm_client) -> TranslationService:
    service = TranslationService()
    service.llm_client = llm_client
    return service


@pytest.mark.asyncio
async def test_llm_error_propagates_instead_of_returning_original():
    service = _make_service(_RaisingLLMClient())

    # __wrapped__ skips the tenacity retry backoff; propagation is the same.
    with pytest.raises(RuntimeError):
        await service.translate_single_post.__wrapped__(service, POST_TEXT)


@pytest.mark.asyncio
async def test_empty_translation_response_raises_value_error():
    service = _make_service(_EmptyResponseLLMClient())

    with pytest.raises(ValueError, match="Empty translation response"):
        await service.translate_single_post.__wrapped__(service, POST_TEXT)


@pytest.mark.asyncio
async def test_cached_translation_returns_without_llm():
    service = _make_service(_RaisingLLMClient())
    service._add_to_cache(f"post:{POST_TEXT}:Unknown", "Harness is infrastructure.")

    result = await service.translate_single_post.__wrapped__(service, POST_TEXT)

    assert result == "Harness is infrastructure."


def test_response_model_reports_translation_status():
    response = SimplifiedPostDetailResponse(
        telegram_message_id=1,
        author_name="Expert",
        message_text="Текст",
        created_at="2026-09-11T00:00:00",
        translation_status="failed",
    )
    assert response.translation_status == "failed"

    default_response = SimplifiedPostDetailResponse(
        telegram_message_id=2,
        author_name="Expert",
        message_text="Текст",
        created_at="2026-09-11T00:00:00",
    )
    assert default_response.translation_status is None
