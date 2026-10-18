#!/usr/bin/env python3
"""Arctic Shift channel: bounded windows, pacing, and graceful degradation.

Measured 2026-10-18 against the live archive: keyword search returns HTTP 422
"Timeout. Maybe slow down a bit" for unbounded windows (and always for very
active subreddits), while a 30-day window answers. The channel therefore has to
send a bounded window on every request, narrow it after a timeout, and never
let one unsupported subreddit take the whole search down.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src import config
from src.services.reddit_enhanced_service import (
    RedditEnhancedService,
    RedditServiceError,
)


def _response(status_code=200, rows=None, headers=None):
    return SimpleNamespace(
        status_code=status_code,
        headers=headers or {},
        json=lambda: {"data": rows or []},
        text="",
    )


def _row(post_id="abc123", subreddit="CommandCode"):
    return {
        "id": post_id,
        "title": f"Thread {post_id}",
        "permalink": f"/r/{subreddit}/comments/{post_id}/thread/",
        "score": 5,
        "num_comments": 2,
        "subreddit": subreddit,
        "author": "someone",
        "created_utc": 1_700_000_000,
        "selftext": "body",
    }


def _service(responses):
    """Service whose HTTP client replays the given responses in order."""
    service = object.__new__(RedditEnhancedService)
    service._arctic_sub_cache = {}
    calls = []

    async def fake_get(url, params=None, **kwargs):
        calls.append({"url": url, "params": dict(params or {})})
        if not responses:
            raise AssertionError("unexpected extra request")
        return responses.pop(0)

    service._get_client = AsyncMock(
        return_value=SimpleNamespace(get=AsyncMock(side_effect=fake_get))
    )
    service.calls = calls
    return service


@pytest.mark.asyncio
async def test_every_request_carries_a_bounded_window(monkeypatch):
    """Unbounded keyword search is what made the channel fail on every search."""
    monkeypatch.setattr(config, "ARCTIC_MAX_SUBSCRIBERS", 0)
    monkeypatch.setattr(config, "ARCTIC_REQUEST_PAUSE_S", 0)
    service = _service([_response(rows=[_row()])])

    posts = await service._search_arctic_shift("GLM 5.3 vs DeepSeek", ["CommandCode"])

    assert [p.id for p in posts] == ["abc123"]
    search_calls = [c for c in service.calls if c["url"].endswith("/posts/search")]
    assert search_calls, "no archive search happened"
    for call in search_calls:
        assert call["params"].get("after"), "request without a bounded time window"
        assert int(call["params"]["limit"]) <= 25
    assert "title" in search_calls[0]["params"]


@pytest.mark.asyncio
async def test_timeout_narrows_the_window_then_gives_up_quietly(monkeypatch):
    monkeypatch.setattr(config, "ARCTIC_MAX_SUBSCRIBERS", 0)
    monkeypatch.setattr(config, "ARCTIC_REQUEST_PAUSE_S", 0)
    service = _service([_response(422), _response(422), _response(422)])

    posts = await service._search_arctic_shift("image generation", ["ChatGPT"])

    assert posts == []  # a load-dependent refusal is not an outage
    windows = [
        c["params"]["after"]
        for c in service.calls
        if c["url"].endswith("/posts/search")
    ]
    assert windows[0] == f"{config.ARCTIC_WINDOW_DAYS}d"
    assert windows[1] == f"{config.ARCTIC_NARROW_WINDOW_DAYS}d"


@pytest.mark.asyncio
async def test_wide_window_timeout_recovers_on_the_narrow_one(monkeypatch):
    monkeypatch.setattr(config, "ARCTIC_MAX_SUBSCRIBERS", 0)
    monkeypatch.setattr(config, "ARCTIC_REQUEST_PAUSE_S", 0)
    service = _service([_response(422), _response(rows=[_row()])])

    posts = await service._search_arctic_shift("GLM latency", ["LocalLLaMA"])

    assert [p.id for p in posts] == ["abc123"]


@pytest.mark.asyncio
async def test_rate_limit_waits_for_the_reset_header(monkeypatch):
    monkeypatch.setattr(config, "ARCTIC_MAX_SUBSCRIBERS", 0)
    monkeypatch.setattr(config, "ARCTIC_REQUEST_PAUSE_S", 0)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("src.services.reddit_enhanced_service.asyncio.sleep", fake_sleep)
    service = _service(
        [
            _response(429, headers={"X-RateLimit-Reset": "7"}),
            _response(rows=[_row()]),
        ]
    )

    posts = await service._search_arctic_shift("GLM", ["CommandCode"])

    assert [p.id for p in posts] == ["abc123"]
    assert 7.0 in slept


@pytest.mark.asyncio
async def test_very_active_subreddit_is_skipped_before_searching(monkeypatch):
    monkeypatch.setattr(config, "ARCTIC_REQUEST_PAUSE_S", 0)
    service = _service(
        [
            _response(rows=[{"subscribers": 9_099_832}]),  # r/ChatGPT membership
            _response(rows=[{"subscribers": 16}]),  # r/seedance membership
            _response(rows=[_row(post_id="small1", subreddit="seedance")]),
        ]
    )

    posts = await service._search_arctic_shift("motion", ["ChatGPT", "seedance"])

    assert [p.id for p in posts] == ["small1"]
    searched_subs = [
        c["params"]["subreddit"]
        for c in service.calls
        if c["url"].endswith("/posts/search")
    ]
    assert searched_subs == ["seedance"]


@pytest.mark.asyncio
async def test_one_broken_subreddit_does_not_lose_the_other(monkeypatch):
    monkeypatch.setattr(config, "ARCTIC_MAX_SUBSCRIBERS", 0)
    monkeypatch.setattr(config, "ARCTIC_REQUEST_PAUSE_S", 0)
    service = _service(
        [
            _response(422),  # r/CommandCode: title, wide
            _response(422),  # narrowed
            _response(422),  # broader query
            _response(rows=[_row(post_id="good", subreddit="seedance")]),
        ]
    )

    posts = await service._search_arctic_shift("motion", ["CommandCode", "seedance"])

    assert [p.id for p in posts] == ["good"]


@pytest.mark.asyncio
async def test_dead_transport_is_still_reported_as_an_outage():
    service = object.__new__(RedditEnhancedService)
    service._arctic_sub_cache = {}
    service._get_client = AsyncMock(side_effect=RuntimeError("offline"))

    with pytest.raises(RedditServiceError, match="All Arctic Shift requests failed"):
        await service._search_arctic_shift("query", ["test"])


@pytest.mark.parametrize(
    "query,anchors,expected",
    [
        ("What do users say about GLM 5.3 latency?", ["GLM 5.3", "latency"], ["GLM 5.3", "latency"]),
        ("How is the motion instruction ignored?", [], ["motion", "instruction", "ignored"]),
        ("What is the best model?", ["GLM"], ["GLM", "model"]),
        ("", [], []),
    ],
)
def test_keywords_are_few_and_free_of_filler(query, anchors, expected):
    assert RedditEnhancedService._arctic_keywords(query, anchors) == expected
