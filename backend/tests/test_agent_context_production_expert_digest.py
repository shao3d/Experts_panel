#!/usr/bin/env python3
"""Production BDD checks for Agent Context expert_digest on Fly.io.

These tests intentionally hit the deployed Experts Panel API. They are skipped
unless AGENT_CONTEXT_PRODUCTION_LIVE=1 is set, so normal local/CI test runs do
not spend live API budget or require network access.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
import requests


BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import load_backend_env


PRODUCTION_API_URL = "https://experts-panel.fly.dev/api/v1/agent/context"
PRODUCTION_TIMEOUT_SECONDS = float(
    os.getenv("AGENT_CONTEXT_PRODUCTION_TIMEOUT_SECONDS", "3600")
)
SUPPORT_LEVELS = {"direct", "indirect", "weak", "unknown"}


class RedactedToken(str):
    def __repr__(self) -> str:
        return "'[redacted-agent-context-token]'"


@pytest.fixture(scope="session")
def production_token() -> RedactedToken:
    if os.getenv("AGENT_CONTEXT_PRODUCTION_LIVE") != "1":
        pytest.skip("Set AGENT_CONTEXT_PRODUCTION_LIVE=1 to hit production Fly.io")

    load_backend_env(BACKEND_DIR / ".env")
    token = os.getenv("AGENT_CONTEXT_API_TOKEN", "").strip()
    if not token:
        pytest.fail("AGENT_CONTEXT_API_TOKEN is required for production live tests")
    return RedactedToken(token)


def test_production_expert_digest_two_experts_is_compact_source_backed(
    production_token: str,
):
    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": (
                "Когда стоит использовать subagents в AI-coding и бизнес-агентах: "
                "где они помогают, а где лучше не усложнять?"
            ),
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "akimov"],
        min_experts_with_sources=2,
    )
    assert response_bytes < 350_000


def test_production_expert_digest_three_experts_preserves_omitted_counts(
    production_token: str,
):
    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": (
                "Как организовать устойчивый AI-coding workflow: subagents, "
                "memory, контекст и разделение планирования с исполнением?"
            ),
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov", "silicbag"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "akimov", "silicbag"],
        min_experts_with_sources=2,
    )
    for expert in payload["experts"]:
        digest = expert["digest"]
        omitted_counts = digest["omitted_counts"]
        assert set(omitted_counts) == {
            "main_sources",
            "linked_context",
            "author_comments",
            "community_comments",
            "external_links",
        }
        assert all(isinstance(value, int) and value >= 0 for value in omitted_counts.values())
    assert response_bytes < 500_000


def test_production_expert_digest_is_smaller_than_source_bundle_for_same_scope(
    production_token: str,
):
    base_payload = {
        "query": (
            "Когда стоит использовать subagents и как отделять планирование "
            "от исполнения?"
        ),
        "expert_scope": "custom",
        "expert_filter": ["refat", "akimov"],
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "include_reddit": False,
        "synthesis_level": "none",
        "use_super_passport": True,
    }

    digest_payload, digest_bytes = _post_agent_context(
        production_token,
        {**base_payload, "response_mode": "expert_digest"},
    )
    source_payload, source_bytes = _post_agent_context(
        production_token,
        {**base_payload, "response_mode": "source_bundle"},
    )

    _assert_expert_digest_contract(
        digest_payload,
        expected_experts=["refat", "akimov"],
        min_experts_with_sources=1,
    )
    assert source_payload["mode"] == "source_bundle"
    assert [expert["expert_id"] for expert in source_payload["experts"]] == [
        "refat",
        "akimov",
    ]
    assert any(expert["main_sources"] for expert in source_payload["experts"])
    assert all(expert["main_sources"] == [] for expert in digest_payload["experts"])
    assert digest_bytes < source_bytes
    assert digest_bytes <= int(source_bytes * 0.75)


def test_production_expert_digest_comments_off_does_not_return_comment_counts(
    production_token: str,
):
    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": (
                "Когда стоит использовать subagents для узких задач, "
                "а когда лучше оставить работу основному агенту?"
            ),
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov"],
            "include_main_source_comments": False,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "akimov"],
        min_experts_with_sources=1,
        include_main_source_comments=False,
    )
    assert "main_source_comments" in payload["pipeline_skipped"]
    for expert in payload["experts"]:
        digest = expert["digest"]
        comments_digest = digest["comments_digest"]
        assert comments_digest["author_comments_count"] == 0
        assert comments_digest["community_comments_count"] == 0
        assert comments_digest["included_comments"] == []
        assert comments_digest["omitted_comments_count"] == 0
        assert digest["omitted_counts"]["author_comments"] == 0
        assert digest["omitted_counts"]["community_comments"] == 0
        for source_ref in digest["source_refs"]:
            assert source_ref["author_comments_count"] == 0
            assert source_ref["community_comments_count"] == 0
    assert response_bytes < 300_000


def test_production_rejects_unknown_expert_before_digest(production_token: str):
    response = _post_agent_context_raw(
        production_token,
        {
            "query": "Когда стоит использовать subagents?",
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["not_a_real_expert"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    assert response.status_code == 400, response.text[:1000]
    payload = response.json()
    assert payload["message"]["unknown_expert_ids"] == ["not_a_real_expert"]


def test_production_rejects_unsupported_response_mode(production_token: str):
    response = _post_agent_context_raw(
        production_token,
        {
            "query": "Когда стоит использовать subagents?",
            "response_mode": "full_answer",
            "expert_scope": "custom",
            "expert_filter": ["refat"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    assert response.status_code == 400, response.text[:1000]
    assert "expert_digest" in str(response.json()["message"])
    assert "source_bundle" in str(response.json()["message"])


def test_production_video_hub_remains_explicitly_unsupported(
    production_token: str,
):
    response = _post_agent_context_raw(
        production_token,
        {
            "query": "Что было в видео про subagents?",
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["video_hub"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    assert response.status_code == 501, response.text[:1000]
    assert "video_hub source_bundle is not implemented" in response.json()["message"]


def _post_agent_context(
    token: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    response = _post_agent_context_raw(token, payload)
    safe_body = response.text[:2000]
    assert response.status_code == 200, safe_body
    parsed = response.json()
    return parsed, len(response.content)


def _post_agent_context_raw(
    token: str,
    payload: dict[str, Any],
) -> requests.Response:
    response = requests.post(
        PRODUCTION_API_URL,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=PRODUCTION_TIMEOUT_SECONDS,
    )
    return response


def _assert_expert_digest_contract(
    payload: dict[str, Any],
    *,
    expected_experts: list[str],
    min_experts_with_sources: int,
    include_main_source_comments: bool = True,
) -> None:
    assert payload["mode"] == "expert_digest"
    assert payload["selection_used"]["expert_scope"] == "custom"
    assert payload["selection_used"]["expert_filter"] == expected_experts
    assert (
        payload["selection_used"]["include_main_source_comments"]
        is include_main_source_comments
    )
    assert payload["selection_used"]["include_drift_comment_groups"] is False
    assert payload["selection_used"]["include_reddit"] is False
    assert payload["selection_used"]["synthesis_level"] == "none"
    assert payload["selection_used"]["use_super_passport"] is True

    assert [expert["expert_id"] for expert in payload["experts"]] == expected_experts
    assert "query_embedding" in payload["pipeline_used"]
    assert "hybrid_retrieval" in payload["pipeline_used"]
    assert "expert_digest_reduce" in payload["pipeline_used"]
    assert "reduce_answer_synthesis" in payload["pipeline_skipped"]
    assert "comment_synthesis" in payload["pipeline_skipped"]
    assert not any(
        "expert_digest_reduce_failed" in warning
        for warning in payload.get("warnings", [])
    )

    experts_with_sources = 0
    for expert in payload["experts"]:
        assert expert["main_sources"] == []
        assert expert["unattached_linked_context"] == []
        assert "comment_id" not in json.dumps(expert, ensure_ascii=False)

        digest = expert.get("digest")
        assert isinstance(digest, dict)
        assert isinstance(digest.get("source_refs"), list)
        assert isinstance(digest.get("key_signals"), list)
        assert isinstance(digest.get("comments_digest"), dict)
        assert isinstance(digest.get("omitted_counts"), dict)

        selected_sources_count = int(expert.get("selected_sources_count") or 0)
        if selected_sources_count <= 0:
            continue

        experts_with_sources += 1
        source_refs = digest["source_refs"]
        source_keys = {source_ref["source_key"] for source_ref in source_refs}
        assert source_refs
        assert len(source_refs) <= 8
        assert digest["key_signals"]
        assert digest.get("position")

        for source_ref in source_refs:
            assert source_ref["source_key"].startswith(f"{expert['expert_id']}:")
            assert source_ref["relevance"] in {"HIGH", "MEDIUM"}
            assert source_ref.get("short_excerpt")
            assert len(source_ref["short_excerpt"]) <= 950
            for external_link in source_ref.get("external_links") or []:
                assert external_link["fetch_status"] == "not_fetched"

        for signal in digest["key_signals"]:
            assert signal["claim"]
            assert signal["support_level"] in SUPPORT_LEVELS
            assert set(signal.get("supporting_sources") or []).issubset(source_keys)

    assert experts_with_sources >= min_experts_with_sources
