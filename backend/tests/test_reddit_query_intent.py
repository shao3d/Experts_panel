import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.api import simplified_query_endpoint as endpoint
from src.api.simplified_query_endpoint import (
    _is_explicit_reddit_synthesis_abstention,
    _parse_reddit_query_plan,
    _sanitize_reddit_source_citations,
)
from src.services.reddit_enhanced_service import RedditEnhancedService, RedditPost


def _post(*, title: str, body: str = "", subreddit: str = "test") -> RedditPost:
    return RedditPost(
        id=title,
        title=title,
        url="https://reddit.com/example",
        permalink="/r/test/example",
        score=10,
        num_comments=8,
        subreddit=subreddit,
        author="user",
        created_utc=1,
        selftext=body,
    )


def test_query_plan_preserves_intent_and_bounded_anchors():
    plan = _parse_reddit_query_plan(
        """```json
        {
          "search_query": "personal mobile voice assistant features people built",
          "user_intent": "practitioner_examples",
          "must_keep": ["personal", "mobile", "features people built", "mobile", 42]
        }
        ```""",
        fallback_query="исходный вопрос",
    )

    assert plan == {
        "search_query": "personal mobile voice assistant features people built",
        "user_intent": "practitioner_examples",
        "must_keep": ["personal", "mobile", "features people built"],
    }


def test_query_plan_falls_back_safely_on_invalid_output():
    assert _parse_reddit_query_plan("not json", "исходный вопрос") == {
        "search_query": "исходный вопрос",
        "user_intent": None,
        "must_keep": [],
    }

    assert _parse_reddit_query_plan('["wrong shape"]', "fallback") == {
        "search_query": "fallback",
        "user_intent": None,
        "must_keep": [],
    }

    unknown_intent = _parse_reddit_query_plan(
        '{"search_query":"voice assistant","user_intent":"invented"}',
        "fallback",
    )
    assert unknown_intent["user_intent"] is None


def test_synthesis_abstention_requires_canonical_standalone_answer():
    assert _is_explicit_reddit_synthesis_abstention(
        "Релевантных обсуждений на Reddit по этой конкретной теме не найдено."
    )
    assert _is_explicit_reddit_synthesis_abstention(
        "No relevant Reddit discussions found for this specific topic."
    )
    assert not _is_explicit_reddit_synthesis_abstention(
        "Some posts were useful, although no relevant benchmarks were found."
    )


def test_out_of_range_synthesis_citations_are_removed_and_disclosed():
    cleaned, invalid = _sanitize_reddit_source_citations(
        "Supported [S1], impossible [S4], and zero [S0].",
        max_source_index=3,
        query_language="English",
    )
    assert "[S1]" in cleaned
    assert "[S4]" not in cleaned
    assert "[S0]" not in cleaned
    assert "failed validation" in cleaned
    assert invalid == [0, 4]


@pytest.mark.asyncio
async def test_english_query_keeps_scout_intent_inference(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        post = SimpleNamespace(
            title="Useful practitioner report",
            permalink="https://reddit.com/r/test/example",
            url="https://reddit.com/r/test/example",
            score=10,
            num_comments=5,
            subreddit="test",
            selftext="Concrete details",
            top_comments=[],
        )
        return SimpleNamespace(posts=[post], total_found=1, processing_time_ms=5)

    async def fake_synthesis(self, query, reddit_result):
        return "Source-grounded answer"

    monkeypatch.setattr(endpoint, "search_reddit_enhanced", fake_search)
    monkeypatch.setattr(endpoint.RedditSynthesisService, "synthesize", fake_synthesis)

    result = await endpoint.process_reddit_pipeline(
        "What features do people build into mobile voice assistants?"
    )

    assert result is not None
    assert captured["original_user_query"].startswith("What features")
    assert captured["user_intent"] is None
    assert captured["must_keep_terms"] == []


@pytest.mark.asyncio
async def test_pipeline_returns_none_for_explicit_synthesis_abstention(monkeypatch):
    post = SimpleNamespace(
        title="Adjacent result",
        permalink="https://reddit.com/r/test/example",
        url="https://reddit.com/r/test/example",
        score=5,
        num_comments=2,
        subreddit="test",
        selftext="Adjacent details",
        top_comments=[],
    )

    async def fake_search(**kwargs):
        return SimpleNamespace(posts=[post], total_found=1, processing_time_ms=5)

    async def fake_synthesis(self, query, reddit_result):
        return "No relevant Reddit discussions found for this specific topic."

    monkeypatch.setattr(endpoint, "search_reddit_enhanced", fake_search)
    monkeypatch.setattr(endpoint.RedditSynthesisService, "synthesize", fake_synthesis)
    assert await endpoint.process_reddit_pipeline("English query") is None


def test_practitioner_discovery_rejects_job_solicitation():
    service = object.__new__(RedditEnhancedService)
    useful = _post(
        title="I built a personal mobile voice assistant with custom shortcuts",
        body="My setup uses custom commands and automations every day.",
    )
    job = _post(
        title="[For Hire] AI Engineer — built production voice assistants",
        body="Open to remote roles and freelance clients.",
        subreddit="MLjobs",
    )

    for post in (useful, job):
        post.heuristic_score = service._score_post_v2(
            post,
            query_terms=["personal", "mobile", "voice", "assistant", "features"],
            anchor_terms=["personal", "mobile"],
            target_keywords=["shortcuts", "automation"],
            intent="practitioner_examples",
        )
        post.final_score = 0.9

    assert useful.heuristic_score > job.heuristic_score
    assert service._apply_confidence_threshold(
        [job, useful],
        target_posts=10,
        require_anchor_match=False,
        intent="practitioner_examples",
    ) == [useful]
    assert service._apply_confidence_threshold(
        [job],
        target_posts=10,
        require_anchor_match=False,
        intent="recommendation",
    ) == [job]


def test_technical_services_title_is_not_penalized_as_promotion():
    service = object.__new__(RedditEnhancedService)
    technical = _post(
        title="Voice assistant controlling local services",
        body="Concrete commands and automations for a personal phone assistant.",
    )
    neutral = _post(
        title="Voice assistant controlling local systems",
        body=technical.selftext,
    )
    scores = [
        service._score_post_v2(
            post,
            query_terms=["voice", "assistant", "local"],
            anchor_terms=["voice", "assistant"],
            target_keywords=["commands", "automations"],
            intent="practitioner_examples",
        )
        for post in (technical, neutral)
    ]
    assert scores[0] == scores[1]


@pytest.mark.asyncio
async def test_details_enrichment_preserves_creation_timestamp(monkeypatch):
    service = object.__new__(RedditEnhancedService)
    service.base_url = "http://reddit-proxy"
    post = _post(title="Discovered result")
    post.created_utc = 0

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "selftext": "Full body",
                "top_comments": [],
                "createdUtc": 1_800_000_000,
            }

    class FakeClient:
        async def post(self, url, json):
            return FakeResponse()

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(service, "_get_client", fake_get_client)
    enriched = await service._enrich_post_content(post)
    assert enriched.created_utc == 1_800_000_000
