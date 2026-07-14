"""Tests for MediumScoringService._parse_text_response missing-post diagnostic.

These tests cover the aggregate WARNING that fires when the LLM's response is missing
posts (likely cause: max_tokens truncation, markdown fence wrapping, or format drift).
The previous per-post log line was replaced with a single aggregate line that includes
the raw response preview for ops diagnostic.
"""

import logging

from src.services.medium_scoring_service import MediumScoringService


def _make_service() -> MediumScoringService:
    """Create a service for tests. LLM client init is defensive and tolerates None."""
    return MediumScoringService(model="gemini-2.5-flash")


def _post(telegram_message_id: int) -> dict:
    return {
        "telegram_message_id": telegram_message_id,
        "content": f"body {telegram_message_id}",
        "author": "x",
        "created_at": "2026-01-01",
    }


def test_parse_text_response_logs_aggregate_warning_when_posts_missing(caplog):
    """When model response omits posts, log ONE aggregate warning with raw preview."""
    svc = _make_service()
    medium_posts = [_post(1), _post(2), _post(3), _post(4), _post(5)]
    # Model only mentions posts 1, 2, 3 — posts 4 and 5 are missing
    raw_content = (
        "=== POST 1 ===\nID: 1\nScore: 0.8\nReason: good\n\n"
        "=== POST 2 ===\nID: 2\nScore: 0.6\nReason: ok\n\n"
        "=== POST 3 ===\nID: 3\nScore: 0.4\nReason: weak\n"
    )
    with caplog.at_level(logging.WARNING, logger="src.services.medium_scoring_service"):
        result = svc._parse_text_response(raw_content, medium_posts, expert_id="ai_architect")

    # All 5 posts present in result
    assert len(result["scored_posts"]) == 5
    # Missing posts got default 0.0
    scores_by_id = {p["telegram_message_id"]: p["score"] for p in result["scored_posts"]}
    assert scores_by_id[4] == 0.0
    assert scores_by_id[5] == 0.0
    # Exactly ONE warning was logged (not one per missing post)
    missing_warnings = [r for r in caplog.records if r.levelname == "WARNING" and "missing" in r.message]
    assert len(missing_warnings) == 1
    # Warning contains count, missing IDs, and raw content preview
    msg = missing_warnings[0].message
    assert "2/5" in msg  # count
    assert "ai_architect" in msg  # expert_id
    assert "ID: 4" not in msg  # missing IDs (we log the IDs, not the content)
    # missing IDs (numeric) should appear
    assert "4" in msg
    assert "5" in msg
    # raw content preview is included (newlines escaped)
    assert "ID: 1" in msg
    assert "\\n" in msg  # newlines were escaped to \\n


def test_parse_text_response_no_warning_when_all_posts_scored(caplog):
    """When model returns all posts, no missing-post warning is logged."""
    svc = _make_service()
    medium_posts = [_post(1), _post(2)]
    raw_content = (
        "=== POST 1 ===\nID: 1\nScore: 0.8\nReason: good\n\n"
        "=== POST 2 ===\nID: 2\nScore: 0.6\nReason: ok\n"
    )
    with caplog.at_level(logging.WARNING, logger="src.services.medium_scoring_service"):
        result = svc._parse_text_response(raw_content, medium_posts, expert_id="ai_architect")

    assert len(result["scored_posts"]) == 2
    missing_warnings = [r for r in caplog.records if r.levelname == "WARNING" and "missing" in r.message]
    assert missing_warnings == []


def test_parse_text_response_truncates_missing_id_list_at_ten(caplog):
    """When >10 posts are missing, the warning lists only the first 10 IDs + '...' suffix."""
    svc = _make_service()
    medium_posts = [_post(i) for i in range(1, 16)]  # 15 posts total
    # Model response only mentions post 1; 14 posts are missing
    raw_content = "=== POST 1 ===\nID: 1\nScore: 0.5\nReason: ok"

    with caplog.at_level(logging.WARNING, logger="src.services.medium_scoring_service"):
        svc._parse_text_response(raw_content, medium_posts, expert_id="ai_architect")

    missing_warnings = [r for r in caplog.records if r.levelname == "WARNING" and "missing" in r.message]
    assert len(missing_warnings) == 1
    msg = missing_warnings[0].message
    assert "14/15" in msg  # 14 missing out of 15
    assert "..." in msg  # truncation marker
