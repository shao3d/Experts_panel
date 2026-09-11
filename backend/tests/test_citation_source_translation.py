#!/usr/bin/env python3
"""Citation verification against the text the user actually sees.

For English queries the cited sources are verified against the same cached
translations the source panel displays, so word-level evidence fragments are
substrings of the translated posts and can be highlighted by the frontend.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.api import simplified_query_endpoint as endpoint
from src.api.simplified_query_endpoint import (
    _run_citation_verification,
    _translate_verification_sources,
)

POST_1 = "Харнес — это инфраструктура вокруг модели."
POST_2 = "Пост, который никто не цитирует."
ANSWER = (
    "The author describes the harness as infrastructure around the model "
    "[post:1]. A claim long enough to count as a statement."
)


class _StubTranslator:
    def __init__(self, failing_texts=()):
        self.calls = []
        self.failing_texts = set(failing_texts)

    async def translate_single_post(self, text, author_name="Unknown"):
        self.calls.append(text)
        if text in self.failing_texts:
            raise RuntimeError("Error code: 402 - Payment Required")
        return f"EN::{text}"


@pytest.mark.asyncio
async def test_only_cited_sources_are_translated(monkeypatch):
    stub = _StubTranslator()
    monkeypatch.setattr(endpoint, "get_translation_service", lambda: stub)

    translated = await _translate_verification_sources(
        "expert", ANSWER, {1: POST_1, 2: POST_2}
    )

    assert stub.calls == [POST_1]  # uncited posts stay untouched
    assert translated[1] == f"EN::{POST_1}"
    assert translated[2] == POST_2


@pytest.mark.asyncio
async def test_failed_translation_falls_back_to_original(monkeypatch):
    stub = _StubTranslator(failing_texts=[POST_1])
    monkeypatch.setattr(endpoint, "get_translation_service", lambda: stub)

    translated = await _translate_verification_sources(
        "expert", ANSWER, {1: POST_1}
    )

    assert translated[1] == POST_1  # fail-open: verify against the original


class _CapturingVerifyService:
    captured = {}

    def __init__(self, model=None):
        pass

    async def verify(self, answer, posts_by_id, expert_id="unknown"):
        type(self).captured = dict(posts_by_id)
        return {"total_count": 1, "evidence": {}}


@pytest.mark.asyncio
async def test_english_query_verifies_against_translations(monkeypatch):
    stub = _StubTranslator()
    monkeypatch.setattr(endpoint, "get_translation_service", lambda: stub)
    monkeypatch.setattr(endpoint, "CitationVerificationService", _CapturingVerifyService)

    await _run_citation_verification(
        "expert", ANSWER, {1: POST_1}, translate_sources=True
    )

    assert _CapturingVerifyService.captured[1] == f"EN::{POST_1}"


@pytest.mark.asyncio
async def test_russian_query_verifies_against_originals(monkeypatch):
    monkeypatch.setattr(endpoint, "CitationVerificationService", _CapturingVerifyService)

    await _run_citation_verification(
        "expert", ANSWER, {1: POST_1}, translate_sources=False
    )

    assert _CapturingVerifyService.captured[1] == POST_1
