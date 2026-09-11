#!/usr/bin/env python3
"""Reddit rerank resilience: an LLM outage must not zero out the results.

Covers the 2026-09 regression where a 402 from the rerank call left every
post with final_score=0.0, the confidence filter abstained on the whole
candidate set, and a search with 18 enriched results was reported as
"no Reddit posts found".
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.services.reddit_enhanced_service import (
    RedditEnhancedService,
    RedditPost,
)

REDDIT_MIN_CONFIDENCE = 0.52
REDDIT_SOFT_CONFIDENCE = 0.44


def _make_service() -> RedditEnhancedService:
    """Build a service instance without network or env dependencies."""
    return object.__new__(RedditEnhancedService)


def _make_post(post_id: str, heuristic_score: float) -> RedditPost:
    return RedditPost(
        id=post_id,
        title=f"Practical harness guide {post_id}",
        url=f"https://reddit.com/r/LocalLLaMA/{post_id}",
        permalink=f"/r/LocalLLaMA/{post_id}",
        score=10,
        num_comments=10,
        subreddit="LocalLLaMA",
        author="practitioner",
        created_utc=1700000000,
        selftext="Hands-on setup steps and trade-offs.",
        heuristic_score=heuristic_score,
    )


class _FailingLLMClient:
    """Stands in for the shared client raising like an exhausted account."""

    async def chat_completions_create(self, **kwargs):
        raise RuntimeError("Error code: 402 - Payment Required")


@pytest.mark.asyncio
async def test_rerank_failure_scores_posts_instead_of_dropping_them():
    service = _make_service()
    service._llm_client = _FailingLLMClient()
    posts = [_make_post("strong", 1.4), _make_post("weak", 0.3)]

    result = await service._ai_rerank_posts("harness setup", posts)

    strong, weak = result
    assert [p.id for p in result] == ["strong", "weak"]  # final_score desc
    assert strong.ai_score == 0.5  # neutral AI component, same as unrated
    assert strong.final_score >= REDDIT_MIN_CONFIDENCE  # survives strict filter
    assert weak.final_score < REDDIT_SOFT_CONFIDENCE  # weak stays filtered
    assert strong.ranking_reason == "LLM rerank unavailable"


def test_score_without_ai_is_deterministic_and_sorted():
    service = _make_service()
    posts = [_make_post("a", 1.4), _make_post("b", 0.9), _make_post("c", 0.3)]

    result = service._score_without_ai(posts)

    scores = [p.final_score for p in result]
    assert scores == sorted(scores, reverse=True)
    assert all(p.ai_score == 0.5 for p in result)
    assert all(p.ranking_reason == "LLM rerank unavailable" for p in result)


def test_fallback_posts_pass_confidence_filter():
    """The regression: a failed rerank left all scores at 0.0 and the
    confidence filter dropped every candidate."""
    service = _make_service()
    posts = [
        _make_post(str(i), score) for i, score in enumerate([1.4, 1.1, 0.8, 0.5])
    ]

    reranked = service._score_without_ai(posts)
    selected = service._apply_confidence_threshold(
        reranked,
        target_posts=4,
        require_anchor_match=False,
        intent="discussion",
    )

    assert selected, "heuristic fallback must not abstain on all candidates"
