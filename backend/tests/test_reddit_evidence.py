"""Regression checks for answer-bearing context and source-local quotes."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.reddit_enhanced_service import RedditEnhancedService, RedditPost
from src.services.reddit_evidence import (
    EvidencePassage,
    RERANK_CONTEXT_CHAR_BUDGET,
    match_evidence,
    select_evidence_passages,
)
from src.services.reddit_synthesis_service import RedditSynthesisService


def post(pid="a", **kwargs):
    fields = dict(
        id=pid, title="Unreal Engine depth export", selftext="Background context.",
        url=f"https://reddit.com/r/test/comments/{pid}/",
        permalink=f"https://reddit.com/r/test/comments/{pid}/",
        score=2000, num_comments=2000, subreddit="test", author="op",
        created_utc=1, heuristic_score=1.4, anchor_matches=2,
    )
    return RedditPost(**{**fields, **kwargs})


def service(ratings):
    instance = object.__new__(RedditEnhancedService)
    instance._llm_client = SimpleNamespace(chat_completions_create=AsyncMock(
        return_value=SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps({"ratings": ratings})),
        )]),
    ))
    return instance


def test_late_body_answer_is_visible_with_bounded_context():
    answer = "For depth export enable the Movie Render Queue additional render passes plugin."
    p = post(selftext="Background information. " * 500 + "\n\n" + answer)
    passages = select_evidence_passages(p, "Unreal Engine depth export Movie Render Queue")
    rendered = "\n".join(x.render() for x in passages)
    assert answer in rendered
    assert len(rendered) <= RERANK_CONTEXT_CHAR_BUDGET
    assert answer not in p.selftext[:320]  # The old judge could not see it.


def test_nested_low_score_answer_and_parent_are_visible():
    answer = "For Z-depth export enable the additional render passes plugin."
    p = post(top_comments=[
        {"body": "Looks great!", "score": 900},
        {"body": "Nice work", "score": 800},
        {"body": "Which setting fixes depth export?", "replies": [
            {"body": answer, "score": 1, "replies": [
                {"body": "No, this failed in the newer version.", "is_op": True},
            ]},
        ]},
    ])
    rendered = "\n".join(x.render() for x in select_evidence_passages(p, "Z-depth export plugin"))
    assert answer in rendered
    assert "Which setting fixes depth export?" in rendered
    assert "No, this failed in the newer version." in rendered
    assert "reply to comment:2" in rendered


def test_selection_does_not_depend_on_popularity():
    p = post(top_comments=[
        {"body": "Unrelated very popular reply " * 100, "score": 10000},
        {"body": "The depth export workaround is to disable multisampling.", "score": -1},
    ])
    assert any("disable multisampling" in x.text for x in select_evidence_passages(p, "depth export workaround"))


def test_elliptical_opening_answer_is_not_lost_to_keyword_rich_body():
    p = post(selftext="Unreal Engine depth export settings. " * 200,
             top_comments=[{"body": "Disable that checkbox and restart the editor."}])
    rendered = "\n".join(x.render() for x in select_evidence_passages(p, "Unreal Engine depth export settings"))
    assert "Disable that checkbox and restart the editor." in rendered
    assert len(rendered) <= RERANK_CONTEXT_CHAR_BUDGET


def test_excerpts_preserve_config_indentation():
    code = "hooks:\n  enabled: true\n  command: ./check.sh"
    p = post(selftext="Working hooks configuration:\n```yaml\n" + code + "\n```")
    rendered = "\n".join(x.render() for x in select_evidence_passages(p, "hooks configuration"))
    assert code in rendered


def test_large_tree_and_body_respect_budget():
    p = post(selftext="depth export " * 10000, top_comments=[
        {"body": "depth export setting " * 1000, "replies": [
            {"body": "depth export failed " * 500} for _ in range(100)
        ]} for _ in range(100)
    ])
    passages = select_evidence_passages(p, "depth export", budget=1800)
    assert len("\n".join(x.render() for x in passages)) <= 1800


@pytest.mark.parametrize("quote", ["A fabricated fix", "exact words from ANOTHER post", "", None, 10])
def test_evidence_must_exist_in_shown_passage(quote):
    assert match_evidence(quote, [EvidencePassage("body:0", "Real fix only")]) is None


def test_quote_normalization_is_narrow_and_source_specific():
    passages = [EvidencePassage("comment:2:0", "Set A &amp; B.\nDo not enable C.")]
    assert match_evidence("Set A & B. Do not enable C.", passages)
    assert not match_evidence("Set A & B. Do enable C.", passages)
    assert not match_evidence("Set A & B.", passages, "body:0")
    assert not match_evidence("Set A & B.", passages, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence", [None, "Enable the magical unicorn switch."])
async def test_popularity_cannot_rescue_missing_or_invented_evidence(evidence):
    s = service([dict(id=0, score=.95, evidence=evidence)])
    ranked = await s._ai_rerank_posts("depth export", [post()])
    assert ranked[0].evidence_status == "missing"
    assert ranked[0].ai_score == .35
    assert ranked[0].final_score > .52  # Old score-only gate admitted it.
    assert not s._apply_confidence_threshold(ranked, 4)


@pytest.mark.asyncio
async def test_quote_from_other_post_does_not_validate():
    s = service([dict(id=0, score=.95, evidence="A unique working setting")])
    ranked = await s._ai_rerank_posts("depth export", [post(), post("b", selftext="A unique working setting")])
    first = next(p for p in ranked if p.id == "a")
    assert first.evidence_status == "missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("score", ["NaN", "Infinity", 3, -1, True, None, "not a number"])
async def test_invalid_rating_is_rejected_without_losing_other_ratings(score):
    s = service([
        dict(id=0, score=score, evidence="Background context."),
        dict(id=1, score=.95, evidence="A real depth export fix"),
    ])
    ranked = await s._ai_rerank_posts("depth export", [post(), post("b", selftext="A real depth export fix")])
    assert next(p for p in ranked if p.id == "a").evidence_status == "invalid_rating"
    assert [p.id for p in s._apply_confidence_threshold(ranked, 4)] == ["b"]


@pytest.mark.asyncio
async def test_duplicate_ids_are_not_silently_overwritten():
    s = service([dict(id=0, score=.95, evidence="Background context.")] * 2)
    ranked = await s._ai_rerank_posts("depth export", [post()])
    assert ranked[0].evidence_status == "invalid_rating"
    assert not s._apply_confidence_threshold(ranked, 4)


@pytest.mark.asyncio
async def test_verified_nested_answer_survives_into_synthesis():
    answer = "Export depth using the additional render passes plugin."
    p = post(top_comments=[{"body": "General conversation"}] * 15 + [
        {"body": "Depth export settings?", "replies": [{"body": answer}]},
    ])
    s = service([dict(id=0, score=.95, evidence=answer)])
    ranked = await s._ai_rerank_posts("depth export render passes", [p])
    assert ranked[0].evidence_status == "verified"
    assert ranked[0].evidence_source.startswith("comment:")
    synth = object.__new__(RedditSynthesisService)
    context = synth._build_context(SimpleNamespace(posts=ranked), 10)
    assert answer in context
    assert "does not establish technical correctness" in context
    assert s._apply_confidence_threshold(ranked, 4)


@pytest.mark.asyncio
async def test_unavailable_judge_is_explicit_and_keeps_existing_fallback():
    s = service([])
    p = post(evidence_status="verified", evidence_span="Old quote", evidence_context="Old context")
    s._llm_client.chat_completions_create.side_effect = RuntimeError("offline")
    ranked = await s._ai_rerank_posts("depth export", [p])
    assert p.evidence_status == "unavailable"
    assert p.evidence_span == p.evidence_context == p.evidence_source == ""
    assert s._apply_confidence_threshold(ranked, 4)
    synth = object.__new__(RedditSynthesisService)
    assert "Ranking degraded" in synth._build_context(SimpleNamespace(posts=ranked), 10)


def test_comment_anchor_gate_sees_nested_answer():
    p = post(title="A useful discovery", selftext="Background", top_comments=[
        {"body": "Great", "replies": [{"body": "depthplugin fixes the export"}]},
    ])
    s = object.__new__(RedditEnhancedService)
    s._score_post_v2(p, ["depthplugin"], ["depthplugin"], [], "how_to")
    assert p.comment_anchor_matches == 1
    assert p.anchor_matches == 1


@pytest.mark.parametrize("reply", ["Thanks, it did not work", "Not fixed", "Worked yesterday, fails today", "Thanks!"])
def test_op_reply_does_not_automatically_certify_solution(reply):
    s = object.__new__(RedditSynthesisService)
    text = s._format_comments_recursive([{"author": "helper", "body": "Try this", "replies": [{"author": "op", "body": reply}]}], post_author="op")
    assert "OP VERIFIED" not in text
    assert reply in text and "[OP]" in text


@pytest.mark.asyncio
async def test_partial_ratings_cannot_promote_omitted_popular_post():
    s = service([dict(id=0, score=.9, evidence="Background context.")])
    ranked = await s._ai_rerank_posts("depth export", [post(), post("omitted")])
    omitted = next(p for p in ranked if p.id == "omitted")
    assert omitted.evidence_status == "invalid_rating"
    assert [p.id for p in s._apply_confidence_threshold(ranked, 4)] == ["a"]
