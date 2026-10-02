"""Search-level regressions: freshness, outages and honest synthesis status."""
import sys
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config
from src.api import simplified_query_endpoint as endpoint
from src.services.reddit_enhanced_service import RedditEnhancedService, RedditPost
from src.services.reddit_service import RedditServiceError
from src.services.reddit_synthesis_service import RedditSynthesisService


def post(pid, age=0, **kwargs):
    data = dict(id=pid, title="Same practical guide", selftext="Detailed settings", url="https://reddit.com/r/test/comments/" + pid,
                permalink="https://reddit.com/r/test/comments/" + pid, score=10, num_comments=5, subreddit="test", author="author",
                created_utc=datetime.utcnow().timestamp()-age*86400)
    return RedditPost(**{**data, **kwargs})


def search_service(monkeypatch, results):
    monkeypatch.setattr(config, "SERPER_API_KEY", "")
    monkeypatch.setattr(config, "ARCTIC_SHIFT_ENABLED", False)
    monkeypatch.setattr(config, "REDDIT_TELEMETRY_ENABLED", False)
    monkeypatch.setattr(config, "REDDIT_REFLECTION_RETRY_ENABLED", False)
    s = object.__new__(RedditEnhancedService)
    async def retrieve():
        if isinstance(results, Exception):
            raise results
        return results
    s._build_search_tasks_v2 = lambda *a, **k: ([("native", retrieve())], {})
    s._search_with_sort = AsyncMock(return_value=[])
    s._enrich_post_content = AsyncMock(side_effect=lambda p: p)
    s._log_debug_trace = lambda *a: None
    async def rank(candidates, remaining, *a):
        return candidates, candidates, [], []
    s._rank_and_filter = AsyncMock(side_effect=rank)
    return s


@pytest.mark.asyncio
@pytest.mark.parametrize("comments", [False, True])
async def test_fresh_same_title_survives_old_duplicate(monkeypatch, comments):
    s = search_service(monkeypatch, [post("old", 200, score=5000), post("fresh", 1)])
    result = await s._search_enhanced_v2("settings", subreddits=[], recent_only=True, include_comments=comments)
    assert [p.id for p in result.posts] == ["fresh"]


@pytest.mark.asyncio
async def test_unknown_or_stale_discovery_dates_never_pass_recent(monkeypatch):
    s = search_service(monkeypatch, [])
    monkeypatch.setattr(config, "SERPER_API_KEY", "test-placeholder")
    s._search_serper = AsyncMock(return_value=[post("unknown", created_utc=0), post("stale", 200)])
    result = await s._search_enhanced_v2("settings", subreddits=[], recent_only=True, include_comments=False)
    assert not result.posts


@pytest.mark.asyncio
async def test_reflection_cannot_reintroduce_old_or_unknown_dates(monkeypatch):
    s = search_service(monkeypatch, [post("initial", 1)])
    monkeypatch.setattr(config, "REDDIT_REFLECTION_RETRY_ENABLED", True)
    s._plan_reflection_retry = AsyncMock(return_value="new settings")
    s._search_with_sort = AsyncMock(return_value=[post("old", 200), post("unknown", created_utc=0), post("fresh", 1)])
    calls = []
    async def rank(candidates, remaining, *args):
        calls.append([p.id for p in candidates])
        return ([] if len(calls) == 1 else candidates), candidates, [], []
    s._rank_and_filter.side_effect = rank
    result = await s._search_enhanced_v2("settings", subreddits=[], recent_only=True)
    assert calls == [["initial"], ["fresh"]]
    assert [p.id for p in result.posts] == ["fresh"]


@pytest.mark.asyncio
async def test_total_retrieval_outage_raises(monkeypatch):
    s = search_service(monkeypatch, RuntimeError("offline"))
    s._search_with_sort.side_effect = RuntimeError("offline")
    with pytest.raises(RedditServiceError, match="All Reddit retrieval channels failed"):
        await s._search_enhanced_v2("settings", subreddits=[])


@pytest.mark.asyncio
async def test_successful_empty_fallback_is_honest_empty(monkeypatch):
    s = search_service(monkeypatch, RuntimeError("offline"))
    result = await s._search_enhanced_v2("settings", subreddits=[])
    assert not result.posts
    assert "fallback_anchor_relevance" in result.strategies_used


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", ["", "  ", None])
async def test_empty_synthesis_is_failed_not_completed(monkeypatch, empty):
    monkeypatch.setattr(endpoint, "search_reddit_enhanced", AsyncMock(return_value=SimpleNamespace(posts=[post("a")], total_found=1, processing_time_ms=1)))
    monkeypatch.setattr(endpoint.RedditSynthesisService, "synthesize", AsyncMock(return_value=empty))
    outcome = await endpoint.run_reddit_search_v2("English query")
    assert outcome.status == "failed"


def test_synthesis_fallback_discloses_failure_and_counts_only_selected():
    text = object.__new__(RedditSynthesisService)._create_fallback_response(SimpleNamespace(posts=[post("a")], total_found=90))
    assert "unavailable" in text
    assert "90" not in text


@pytest.mark.asyncio
async def test_gemini_success_reaches_model_and_does_not_use_fallback():
    s = object.__new__(RedditSynthesisService)
    s._generate_completion = AsyncMock(return_value=(json.dumps({"requirements": [{"requirement": "Answer", "supported": True}], "coverage": "sufficient", "gap": "", "findings": [{"text": "A grounded answer", "sources": [1], "kind": "reported"}], "actions": []}), "stop"))
    answer = await s._synthesize_gemini("query", [], SimpleNamespace(posts=[post("a")], total_found=90), "English", 10, backend="gemini")
    assert "A grounded answer [S1]" in answer
    s._generate_completion.assert_awaited_once()


def test_synthesis_source_numbers_do_not_leak_rerank_positions():
    p = post("a", evidence_status="verified", evidence_context="[p17/comment:9:0] Exact source text")
    context = object.__new__(RedditSynthesisService)._build_context(SimpleNamespace(posts=[p]), 10)
    assert "[S1]" in context and "p17/" not in context
    assert "Exact source text" in context


@pytest.mark.asyncio
async def test_discovery_placeholder_cannot_hide_fresh_same_title(monkeypatch):
    s = search_service(monkeypatch, [])
    monkeypatch.setattr(config, "SERPER_API_KEY", "test-placeholder")
    s._search_serper = AsyncMock(return_value=[post("unknown", created_utc=0), post("fresh", 1)])
    result = await s._search_enhanced_v2("settings", subreddits=[], recent_only=True, include_comments=True)
    assert [p.id for p in result.posts] == ["fresh"]


@pytest.mark.asyncio
async def test_serper_outage_propagates_instead_of_empty_results():
    s = object.__new__(RedditEnhancedService)
    s._get_client = AsyncMock(side_effect=RuntimeError("offline"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "SERPER_API_KEY", "test-placeholder")
        with pytest.raises(RedditServiceError, match="Serper retrieval failed"):
            await s._search_serper("query")


@pytest.mark.asyncio
async def test_arctic_total_outage_propagates():
    s = object.__new__(RedditEnhancedService)
    s._get_client = AsyncMock(side_effect=RuntimeError("offline"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "ARCTIC_SHIFT_ENABLED", True)
        with pytest.raises(RedditServiceError, match="All Arctic Shift requests failed"):
            await s._search_arctic_shift("query", ["test"])
