#!/usr/bin/env python3
"""The candidate cut decides what the judge can ever see.

Measured 2026-10-18: the median search has 134 unique candidates and only
REDDIT_RERANK_CANDIDATES (18) of them reach the answerability judge. The
heuristic score rewards anchor-word overlap, so one strategy or one subreddit
can take the whole slate while the best finds of other channels are dropped
unjudged.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src import config
from src.services.reddit_enhanced_service import RedditEnhancedService, RedditPost


def post(index, strategy="scout_global_relevance", subreddit="LocalLLaMA"):
    return RedditPost(
        id=f"p{index}",
        title=f"Post {index}",
        url=f"https://reddit.com/p{index}",
        permalink=f"https://reddit.com/p{index}",
        score=10,
        num_comments=3,
        subreddit=subreddit,
        author="author",
        created_utc=1_700_000_000 + index,
        heuristic_score=1.0 - index / 1000,
        found_by_strategy=strategy,
        strategy_hits=[strategy],
    )


def distinct_rule(judged, dropped):
    """Every judged post keeps heuristic order and nothing is duplicated."""
    ids = [p.id for p in judged]
    assert len(ids) == len(set(ids))
    assert not (set(ids) & {p.id for p in dropped})
    assert ids == [p.id for p in judged]


def test_zero_reserve_is_the_plain_heuristic_cut():
    pool = [post(i) for i in range(30)]
    judged, dropped = RedditEnhancedService._split_rerank_candidates(
        pool, limit=18, reserved=0
    )
    assert [p.id for p in judged] == [f"p{i}" for i in range(18)]
    assert [p.id for p in dropped] == [f"p{i}" for i in range(18, 30)]
    distinct_rule(judged, dropped)


def test_reserve_brings_in_strategies_the_top_never_reached():
    pool = [post(i, strategy="scout_global_relevance") for i in range(18)]
    pool += [post(100, strategy="comparison_anchor_relevance", subreddit="nvidia")]
    pool += [post(101, strategy="serp_google_discovery", subreddit="DeepSeek")]
    pool += [post(102, strategy="targeted_scout_relevance", subreddit="seedance")]
    pool += [post(i, strategy="quality_targeted_top") for i in range(200, 210)]

    judged, dropped = RedditEnhancedService._split_rerank_candidates(
        pool, limit=18, reserved=4
    )

    assert len(judged) == 18
    assert len(dropped) == len(pool) - 18
    strategies = {p.found_by_strategy for p in judged}
    assert {"comparison_anchor_relevance", "serp_google_discovery", "targeted_scout_relevance"} <= strategies
    # The heuristic head keeps its order and its size minus the reserve.
    assert [p.id for p in judged[:14]] == [f"p{i}" for i in range(14)]
    distinct_rule(judged, dropped)


def test_reserve_covers_subreddits_when_strategies_are_already_present():
    pool = [post(i, strategy="scout_global_relevance", subreddit="LocalLLaMA") for i in range(18)]
    pool += [post(100, strategy="scout_global_relevance", subreddit="seedance")]
    pool += [post(101, strategy="scout_global_relevance", subreddit="CommandCode")]

    judged, _ = RedditEnhancedService._split_rerank_candidates(pool, limit=18, reserved=2)

    assert [p.id for p in judged[-2:]] == ["p100", "p101"]


def test_unused_reserve_falls_back_to_heuristic_order():
    pool = [post(i) for i in range(25)]
    judged, dropped = RedditEnhancedService._split_rerank_candidates(
        pool, limit=18, reserved=4
    )
    # No unseen strategy exists, so the reserve must not leave holes.
    assert [p.id for p in judged] == [f"p{i}" for i in range(18)]
    assert len(dropped) == 7
    distinct_rule(judged, dropped)


@pytest.mark.parametrize("size,limit,reserved", [(3, 18, 4), (18, 18, 4), (1, 18, 4)])
def test_pools_smaller_than_the_limit_are_untouched(size, limit, reserved):
    pool = [post(i) for i in range(size)]
    judged, dropped = RedditEnhancedService._split_rerank_candidates(
        pool, limit=limit, reserved=reserved
    )
    assert [p.id for p in judged] == [p.id for p in pool]
    assert dropped == []


def test_reserve_never_takes_the_whole_slate():
    pool = [post(i) for i in range(30)]
    judged, _ = RedditEnhancedService._split_rerank_candidates(pool, limit=4, reserved=4)
    assert len(judged) == 4  # at least one heuristic slot always survives
    assert judged[0].id == "p0"


def test_default_config_keeps_the_old_behaviour():
    """The diversity cut ships disabled: it needs its own measurement first."""
    assert config.REDDIT_RERANK_DIVERSITY_SLOTS == 0
