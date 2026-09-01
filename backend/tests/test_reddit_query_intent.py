import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.api import simplified_query_endpoint as endpoint
from src.api.simplified_query_endpoint import _parse_reddit_query_plan
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
