"""Regression checks for the dsh-vs-Gemini A/B harness helpers.

These cover the parts that decide what the comparison *means*: which questions
enter the reference set, how the agreement metric is computed, and whether a
RedditPost survives the fixture round-trip with its comment tree intact.
"""

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src.services.reddit_enhanced_service import RedditPost  # noqa: E402


def load_harness():
    spec = importlib.util.spec_from_file_location(
        "ab_reddit_harness", BACKEND / "scripts" / "ab_reddit_dsh_vs_gemini.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = load_harness()


def telemetry(tmp_path: Path, records) -> Path:
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8"
    )
    return path


def test_load_reference_keeps_most_recent_unique_questions(tmp_path):
    path = telemetry(
        tmp_path,
        [
            {"query": "old question", "plan_query": "old", "winners": []},
            {"query": "repeat", "plan_query": "first", "winners": []},
            {"query": "repeat", "plan_query": "second", "winners": []},
            {"query": "newest", "plan_query": "newest", "winners": []},
        ],
    )
    picked = harness.load_reference(path, limit=2)
    assert [r["query"] for r in picked] == ["newest", "repeat"]
    # The newest record wins for a repeated question.
    assert picked[1]["plan_query"] == "second"


def test_reference_winners_ignores_entries_without_id():
    record = {"winners": [{"id": "abc"}, {"subreddit": "x"}, {"id": ""}, {"id": "def"}]}
    assert harness.reference_winners(record) == ["abc", "def"]


def test_fixture_path_is_stable_and_filesystem_safe():
    record = {"plan_query": "What is dsh-cli / DeepSeek Harness?", "query": "ignored"}
    path = harness.fixture_path(record)
    assert path.name == "what-is-dsh-cli-deepseek-harness.json"
    assert harness.fixture_path(record) == path


def test_post_survives_the_fixture_round_trip():
    original = RedditPost(
        id="abc",
        title="Depth export",
        url="https://reddit.com/r/test/comments/abc/",
        permalink="https://reddit.com/r/test/comments/abc/",
        score=10,
        num_comments=4,
        subreddit="test",
        author="op",
        created_utc=1,
        selftext="body",
        strategy_hits=["literal_global_relevance"],
        top_comments=[{"body": "comment", "replies": [{"body": "nested"}]}],
    )
    restored = RedditPost(**json.loads(json.dumps(dataclasses.asdict(original))))
    assert restored == original
    assert restored.top_comments[0]["replies"][0]["body"] == "nested"


def test_agreement_counts_only_winners_still_in_the_pool():
    """Regression: agreement must not be diluted by retrieval drift."""
    runs = [[
        {
            "query": "q", "intent": "how_to", "candidates": 18, "judge_latency_s": 9.0,
            "verified": 12, "verified_rate": 0.667, "unrated": 0, "invalid": 0,
            "selected": ["keep", "fresh"], "selected_count": 2,
            "gemini_winners": ["keep", "gone"], "gemini_selected": 2,
            "available": ["keep"], "agreed": ["keep"], "agreement": 1.0,
            "top_scores": [],
        }
    ]]
    report = harness.summarize(runs)
    assert report["agreement_mean"] == 1.0
    assert report["gemini_winners_still_in_pool"] == 0.5
    assert report["verified_rate_mean"] == 0.667
    assert report["abstains"] == 0


def test_summary_flags_abstains_on_both_sides():
    runs = [[
        {
            "query": "q", "intent": "comparison", "candidates": 5, "judge_latency_s": 8.0,
            "verified": 5, "verified_rate": 1.0, "unrated": 0, "invalid": 0,
            "selected": [], "selected_count": 0,
            "gemini_winners": [], "gemini_selected": 0,
            "available": [], "agreed": [], "agreement": None,
            "top_scores": [],
        }
    ]]
    report = harness.summarize(runs)
    assert report["abstains"] == 1
    assert report["gemini_abstains"] == 1
    assert report["agreement_mean"] is None


@pytest.mark.asyncio
async def test_harness_mirrors_the_pipeline_on_a_judge_outage(monkeypatch):
    """An unrated pool must degrade visibly, not abstain (see _rank_and_filter)."""
    from src.services.reddit_enhanced_service import (
        RedditEnhancedService,
        RedditPost,
    )

    unrated = RedditPost(
        id="a", title="t", url="u", permalink="p", score=1, num_comments=1,
        subreddit="s", author="op", created_utc=1, heuristic_score=1.4,
        anchor_matches=2, final_score=0.9, evidence_status="unavailable",
    )

    async def fake_rerank(*args, **kwargs):
        return [unrated]

    service = object.__new__(RedditEnhancedService)
    monkeypatch.setattr(service, "_ai_rerank_posts", fake_rerank)

    fixture = {
        "query": "q", "plan_query": "q", "anchor_terms": [],
        "search_plan": {"intent": "how_to"}, "gemini_winners": [],
        "gemini_selected": 0,
        "candidates": [{"id": "a", "title": "t", "url": "u", "permalink": "p",
                        "score": 1, "num_comments": 1, "subreddit": "s",
                        "author": "op", "created_utc": 1}],
    }
    row = await harness.judge_once(service, fixture)

    assert row["judge_unavailable"] is True
    assert row["decision_tier"] == "soft"
    assert row["selected"] == ["a"]
    assert harness.summarize([[row]])["judge_outage_questions"] == 1
