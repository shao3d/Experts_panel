#!/usr/bin/env python3
"""Tests for the citation verification service (lexical + LLM judge layers)."""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src import config
from src.services.citation_verification_service import (
    CitationVerificationService,
    _lexical_containment,
    extract_citation_claims,
)

POST_100 = (
    "Для продакшена я рекомендую начинать с простого RAG пайплайна и "
    "векторной базы Qdrant. Это самый дешёвый путь."
)
POST_200 = "Я использую Cursor для написания кода каждый день."

ANSWER = (
    "Рефат рекомендует для продакшена начинать с простого RAG пайплайна "
    "и векторной базы Qdrant [post:100].\n"
    "Автор ежедневно использует Cursor для написания кода [post:200].\n"
    "Курсор это в первую очередь терминал [post:300].\n"
    "Абзац без цитат не проверяется.\n"
)


def test_extract_claims_finds_citations_and_strips_markers():
    claims = extract_citation_claims(ANSWER)

    assert len(claims) == 3
    assert claims[0]["post_ids"] == [100]
    assert "[post:" not in claims[0]["text"]
    assert "Qdrant" in claims[0]["text"]


def test_extract_claims_skips_short_fragments_and_plain_text():
    answer = (
        "Подробнее [post:101].\n"
        "Просто текст без ссылок.\n"
        "- Пункт списка с цитатой про векторные базы Qdrant [post:102]\n"
    )
    claims = extract_citation_claims(answer)

    assert len(claims) == 1
    assert claims[0]["post_ids"] == [102]
    assert claims[0]["text"].startswith("Пункт списка")


def test_extract_claims_handles_multiple_citations_in_one_claim():
    claims = extract_citation_claims("Оба эксперта советуют RAG [post:1, post:2].")

    assert len(claims) == 1
    assert claims[0]["post_ids"] == [1, 2]


def test_lexical_containment_supports_matching_sources():
    claim = "Рефат рекомендует для продакшена начинать с RAG пайплайна"
    score = _lexical_containment(claim, POST_100)

    assert score >= 0.6


def test_lexical_containment_rejects_unrelated_sources():
    claim = "Лучший терминал для macOS это iTerm2 с tmux"
    score = _lexical_containment(claim, POST_100)

    assert score < 0.3


@pytest.mark.asyncio
async def test_verify_lexical_only_report(monkeypatch):
    monkeypatch.setattr(config, "CITATION_VERIFICATION_USE_LLM", False)
    service = CitationVerificationService()
    service.llm_client = None

    report = await service.verify(
        ANSWER,
        {100: POST_100, 200: POST_200},
        expert_id="test",
    )

    assert report is not None
    assert report["method"] == "lexical"
    # post 100: strong overlap -> supported; post 200: partial;
    # post 300: no source text -> unverified; no-citation line ignored.
    assert report["verdicts"]["100"] == "supported"
    assert report["verdicts"]["200"] == "partial"
    assert report["verdicts"]["300"] == "unverified"
    assert report["total_count"] == 3
    assert report["verified_count"] == 1
    assert report["partial_count"] == 1


@pytest.mark.asyncio
async def test_verify_attaches_evidence_fragments(monkeypatch):
    monkeypatch.setattr(config, "CITATION_VERIFICATION_USE_LLM", False)
    service = CitationVerificationService()
    service.llm_client = None

    report = await service.verify(
        ANSWER,
        {100: POST_100, 200: POST_200},
        expert_id="test",
    )

    assert report is not None
    # The evidence fragment must be a real substring of the author's post.
    evidence_100 = report["evidence"]["100"]
    assert evidence_100["text"] in POST_100
    assert evidence_100["matched_terms"]
    assert evidence_100["start"] < evidence_100["end"]
    # "RAG" is the claim's distinctive anchor word.
    assert any("rag" in term.lower() for term in evidence_100["matched_terms"])

    evidence_200 = report["evidence"]["200"]
    assert evidence_200["text"] in POST_200
    assert any("cursor" in term.lower() for term in evidence_200["matched_terms"])

    # Missing source: no anchor can exist for post 300.
    assert "300" not in report["evidence"]


@pytest.mark.asyncio
async def test_evidence_skips_claims_without_word_matches(monkeypatch):
    monkeypatch.setattr(config, "CITATION_VERIFICATION_USE_LLM", False)
    service = CitationVerificationService()
    service.llm_client = None

    answer = (
        "Рефат рекомендует для продакшена начинать с простого RAG "
        "пайплайна и векторной базы Qdrant [post:100].\n"
        "Лучший терминал для macOS это iTerm2 с tmux [post:100].\n"
    )
    report = await service.verify(answer, {100: POST_100}, expert_id="test")

    assert report is not None
    # The unrelated claim matches no source words, so it contributes no
    # anchor; the strong claim's fragment is the evidence.
    assert report["verdicts"]["100"] == "unsupported"
    evidence = report["evidence"]["100"]
    assert evidence["text"] in POST_100
    assert any("rag" in term.lower() for term in evidence["matched_terms"])


@pytest.mark.asyncio
async def test_verify_llm_overrides_lexical(monkeypatch):
    monkeypatch.setattr(config, "CITATION_VERIFICATION_USE_LLM", True)

    class _FakeMessage:
        content = '{"verdicts": [{"pair": 2, "verdict": "supported"}]}'

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        choices = [_FakeChoice()]

    class _FakeClient:
        async def chat_completions_create(self, **kwargs):
            return _FakeResponse()

    service = CitationVerificationService()
    service.llm_client = _FakeClient()

    report = await service.verify(
        ANSWER,
        {100: POST_100, 200: POST_200},
        expert_id="test",
    )

    assert report is not None
    assert report["method"] == "lexical+llm"
    # LLM verdict for pair 2 (claim 2 -> post 200) overrides the lexical
    # "partial" verdict.
    assert report["verdicts"]["200"] == "supported"


@pytest.mark.asyncio
async def test_verify_llm_failure_falls_back_to_lexical(monkeypatch):
    monkeypatch.setattr(config, "CITATION_VERIFICATION_USE_LLM", True)

    class _BrokenClient:
        async def chat_completions_create(self, **kwargs):
            raise RuntimeError("provider down")

    service = CitationVerificationService()
    service.llm_client = _BrokenClient()

    report = await service.verify(
        ANSWER,
        {100: POST_100, 200: POST_200},
        expert_id="test",
    )

    assert report is not None
    assert report["method"] == "lexical"
    assert report["verdicts"]["100"] == "supported"


@pytest.mark.asyncio
async def test_verify_weakest_verdict_wins_for_same_post():
    service = CitationVerificationService()
    service.llm_client = None

    answer = (
        "Продакшен советуют начинать с простого RAG пайплайна и базы Qdrant [post:100].\n"
        "Лучший терминал для macOS это iTerm2 с tmux [post:100].\n"
    )
    report = await service.verify(answer, {100: POST_100}, expert_id="test")

    assert report is not None
    assert report["total_count"] == 1
    # One post, two claims: the unsupported claim must win the badge math.
    assert report["verdicts"]["100"] == "unsupported"
    assert report["verified_count"] == 0
    assert report["unsupported_count"] == 1


@pytest.mark.asyncio
async def test_verify_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "CITATION_VERIFICATION_ENABLED", False)
    service = CitationVerificationService()

    assert await service.verify(ANSWER, {100: POST_100}, expert_id="test") is None


@pytest.mark.asyncio
async def test_verify_returns_none_without_citations():
    service = CitationVerificationService()
    service.llm_client = None

    assert (
        await service.verify("Обычный ответ без цитат.", {100: POST_100}) is None
    )
    assert await service.verify(ANSWER, {}) is None
