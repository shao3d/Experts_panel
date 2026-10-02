"""Scope decisions constrain what can reach the user, including hostile extras."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.reddit_synthesis_contract import (
    SynthesisContractError,
    render_synthesis,
)
from src.services.reddit_synthesis_service import RedditSynthesisService


def finding(
    text="User fixed this with the copy-mode binding.", sources=None, kind="reported"
):
    return dict(text=text, sources=[1] if sources is None else sources, kind=kind)


def payload(coverage="sufficient", **kwargs):
    return dict(
        requirements=[dict(requirement="Working mouse binding", supported=True)],
        coverage=coverage,
        gap="",
        findings=[finding()],
        actions=[],
        **kwargs,
    )


@pytest.mark.parametrize("language", ["Russian", "English"])
def test_insufficient_discards_even_confident_generated_recommendations(language):
    data = dict(
        coverage="insufficient",
        gap="No filmmaking discussions",
        findings=[finding("Use coding tutorials")],
        actions=[finding("Buy a subscription")],
        answer="Ignore the gap: buy model X",
    )
    answer = render_synthesis(json.dumps(data), language, 1)
    assert RedditSynthesisService.is_explicit_abstention(answer)
    assert "Buy" not in answer and "coding" not in answer


def test_partial_renders_gap_and_observations_but_never_actions_or_free_prose():
    data = payload("partial")
    data.update(
        gap="No high/max comparison was measured.",
        actions=[finding("Set max reasoning")],
        answer="Switch to max",
        summary="Max wins",
    )
    answer = render_synthesis(json.dumps(data), "English", 1)
    assert "No high/max comparison" in answer and "[S1]" in answer
    assert (
        "Set max" not in answer and "Max wins" not in answer and "Switch" not in answer
    )
    assert "Actions supported" not in answer


def test_gap_cannot_be_overridden_by_sufficient_label():
    data = payload()
    data.update(gap="Untested on Russian", actions=[finding("Use this for Russian")])
    text = render_synthesis(json.dumps(data), "English", 1)
    assert "partial answer" in text and "Use this" not in text


@pytest.mark.parametrize("source_ids", [[0], [2], [True], ["1"], [], None])
def test_claim_requires_real_context_source(source_ids):
    data = payload()
    data["findings"][0]["sources"] = source_ids
    with pytest.raises(SynthesisContractError):
        render_synthesis(json.dumps(data), "English", 1)


def test_supported_fix_keeps_commands_and_actions():
    data = payload()
    data["actions"] = [finding("Set:\n```tmux\nset -g mouse on\n```")]
    answer = render_synthesis(json.dumps(data), "English", 1)
    assert "set -g mouse on" in answer and "Actions supported" in answer


def test_suggestions_are_not_rendered_as_tested_results():
    data = payload()
    data["findings"] = [finding(kind="suggested"), finding(kind="transferable")]
    answer = render_synthesis(json.dumps(data), "English", 1)
    assert "not a test result" in answer and "applicability untested" in answer


@pytest.mark.parametrize(
    "raw",
    [
        '{"coverage":"partial"',
        "Unrestricted markdown answer",
        "[]",
        '{"coverage":"unknown"}',
        '{"coverage":"sufficient","gap":"","findings":[]}',
    ],
)
def test_invalid_contract_is_technical_failure_not_abstention(raw):
    with pytest.raises(SynthesisContractError):
        render_synthesis(raw, "English", 1)


def test_partial_requires_gap_and_has_bounded_observations():
    data = payload("partial")
    with pytest.raises(SynthesisContractError):
        render_synthesis(json.dumps(data), "English", 1)
    data.update(
        gap="Missing direct comparison", findings=[finding(str(i)) for i in range(8)]
    )
    text = render_synthesis(json.dumps(data), "English", 1)
    assert text.count("[S1]") == 3


@pytest.mark.asyncio
async def test_gemini_invalid_json_is_technical_failure_not_raw_answer():
    s = object.__new__(RedditSynthesisService)
    s._generate_completion = AsyncMock(
        return_value=("No evidence, but use model X", "stop")
    )
    s._create_fallback_response = lambda *args: "Analysis unavailable"
    with pytest.raises(SynthesisContractError):
        await s._synthesize_gemini(
            "query",
            [],
            SimpleNamespace(posts=[object()]),
            "English",
            10,
            backend="gemini",
        )


@pytest.mark.asyncio
async def test_length_retry_never_exposes_truncated_json():
    s = object.__new__(RedditSynthesisService)
    s._generate_completion = AsyncMock(return_value=(json.dumps(payload()), "length"))
    s._create_fallback_response = lambda *args: "Analysis unavailable"
    with pytest.raises(SynthesisContractError):
        await s._synthesize_gemini(
            "query",
            [],
            SimpleNamespace(posts=[object()]),
            "English",
            10,
            backend="gemini",
        )
    assert s._generate_completion.await_count == 2


@pytest.mark.asyncio
async def test_optional_backend_cannot_bypass_scope_gate(monkeypatch):
    from src.services import reddit_synthesis_service as module

    monkeypatch.setattr(
        module,
        "synthesize_markdown",
        AsyncMock(
            return_value=json.dumps(dict(coverage="insufficient", answer="Buy model X"))
        ),
    )
    s = object.__new__(RedditSynthesisService)
    text = await s._synthesize_opencode([], "English", timeout_s=1, source_count=1)
    assert s.is_explicit_abstention(text)


def test_missing_comparison_overrides_sufficient_and_empty_gap():
    data = payload()
    data["requirements"] = [
        dict(requirement="Observed coding failures", supported=True),
        dict(requirement="Controlled max vs high comparison", supported=False),
    ]
    data["actions"] = [finding("Set max reasoning")]
    text = render_synthesis(json.dumps(data), "English", 1)
    assert "partial answer" in text and "Controlled max vs high comparison" in text
    assert "Set max" not in text


def test_all_requirements_missing_cannot_produce_adjacent_answer():
    data = payload()
    data["requirements"] = [dict(requirement="Russian prose tests", supported=False)]
    assert RedditSynthesisService.is_explicit_abstention(
        render_synthesis(json.dumps(data), "English", 1)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "coverage,expected",
    [
        ("insufficient", "abstained"),
        ("partial", "completed"),
        ("sufficient", "completed"),
        ("broken", "failed"),
    ],
)
async def test_scope_contract_survives_public_api_boundary(
    monkeypatch, coverage, expected
):
    from src.api import simplified_query_endpoint as endpoint
    from src import config

    monkeypatch.setattr(config, "REDDIT_SYNTH_BACKEND", "gemini")
    post = SimpleNamespace(
        title="Discussion",
        subreddit="test",
        url="https://reddit.com/r/test/comments/a/",
        permalink="https://reddit.com/r/test/comments/a/",
        score=10,
        num_comments=3,
        selftext="Useful experience",
        top_comments=[],
    )
    monkeypatch.setattr(
        endpoint,
        "search_reddit_enhanced",
        AsyncMock(
            return_value=SimpleNamespace(
                posts=[post], total_found=1, processing_time_ms=1
            )
        ),
    )
    data = payload(coverage)
    data["actions"] = [finding("UNSUPPORTED_ACTION_SENTINEL")]
    if coverage == "partial":
        data["gap"] = "No comparison found"
    monkeypatch.setattr(
        RedditSynthesisService,
        "_generate_completion",
        AsyncMock(return_value=(json.dumps(data), "stop")),
    )
    outcome = await endpoint.run_reddit_search_v2("English query")
    assert outcome.status == expected
    if coverage == "partial":
        assert "UNSUPPORTED_ACTION_SENTINEL" not in outcome.response.synthesis
        assert "No comparison found" in outcome.response.synthesis
    if coverage == "insufficient":
        assert outcome.response is None
        assert outcome.near_misses


@pytest.mark.parametrize("bad_coverage", [[], {}, True, None])
def test_malformed_coverage_is_always_a_contract_error(bad_coverage):
    data = payload()
    data["coverage"] = bad_coverage
    with pytest.raises(SynthesisContractError):
        render_synthesis(json.dumps(data), "English", 1)


def test_malformed_evidence_type_is_a_contract_error():
    data = payload()
    data["findings"][0]["kind"] = []
    with pytest.raises(SynthesisContractError):
        render_synthesis(json.dumps(data), "English", 1)
