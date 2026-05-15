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
PRODUCTION_EXPAND_API_URL = "https://experts-panel.fly.dev/api/v1/agent/context/expand"
PRODUCTION_TIMEOUT_SECONDS = float(
    os.getenv("AGENT_CONTEXT_PRODUCTION_TIMEOUT_SECONDS", "3600")
)
SUPPORT_LEVELS = {"direct", "indirect", "weak", "unknown"}
EVIDENCE_DEPTHS = {"deep_practical", "moderate", "shallow", "unknown"}
EVIDENCE_SOURCE_TYPES = {
    "practitioner_experience",
    "tool_release",
    "announcement",
    "mention",
    "analysis",
    "unknown",
}
EVIDENCE_COMMENT_SIGNALS = {
    "author_support",
    "community_support",
    "mixed",
    "mostly_noise",
    "none",
    "unknown",
}
EVIDENCE_CONFIDENCES = {"high", "medium", "low"}
TECH_BUSINESS_EXPERTS = [
    "ai_grabli",
    "refat",
    "akimov",
    "llm_under_hood",
    "elkornacio",
    "doronin",
    "air_ai",
    "silicbag",
    "kornish",
]


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


def test_production_expert_digest_carries_evidence_quality_calibration(
    production_token: str,
):
    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": (
                "Когда subagents реально помогают в AI-разработке, "
                "а когда только создают лишнюю сложность?"
            ),
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "doronin"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "doronin"],
        min_experts_with_sources=2,
    )
    source_qualities = [
        source_ref["evidence_quality"]
        for expert in payload["experts"]
        for source_ref in expert["digest"]["source_refs"]
    ]
    assert source_qualities
    assert any(quality["depth"] != "unknown" for quality in source_qualities)
    assert any(
        quality["confidence"] in {"medium", "high"}
        for quality in source_qualities
    )
    assert response_bytes < 400_000


def test_production_expert_digest_handles_casual_ru_typo_query_and_forces_embeddings(
    production_token: str,
):
    query = (
        "Панэкс, по-человечески: когда сабагенты реально помогают, "
        "а когда они только мешают? Без воды, как для кодинга."
    )

    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": query,
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": False,
        },
    )

    assert payload["query"] == query
    assert payload["selection_used"]["use_super_passport"] is True
    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "akimov"],
        min_experts_with_sources=2,
    )
    _assert_no_retrieval_parser_failure_warnings(payload)
    assert response_bytes < 400_000


def test_production_expert_digest_survives_mixed_ru_en_punctuation_query(
    production_token: str,
):
    query = (
        "Что такое file-fist / file-first подход? Почему embeddings - это не "
        "всегда хорошо для поиска? context rot, FTS5, RAG, Claude Code."
    )

    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": query,
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "doronin", "kornish"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    assert payload["query"] == query
    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "doronin", "kornish"],
        min_experts_with_sources=2,
    )
    _assert_no_retrieval_parser_failure_warnings(payload)
    assert response_bytes < 550_000


def test_production_expert_digest_handles_long_pm_style_multiline_query(
    production_token: str,
):
    query = (
        "Мне нужно принять рабочее решение для AI-coding процесса.\n"
        "- когда заводить subagents;\n"
        "- когда держать одного главного агента;\n"
        "- как не словить context rot;\n"
        "- где memory, tests, review и стоимость начинают мешать.\n"
        "Дай практическую картину без маркетинга."
    )

    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": query,
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov", "doronin"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    assert payload["query"] == query
    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "akimov", "doronin"],
        min_experts_with_sources=2,
    )
    _assert_no_retrieval_parser_failure_warnings(payload)
    assert response_bytes < 650_000


def test_production_expert_digest_handles_real_group_scope_request(
    production_token: str,
):
    query = (
        "По всем экспертам группы Tech & Business: что такое context rot, "
        "почему он ломает AI-разработку и какие практики реально помогают?"
    )

    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": query,
            "response_mode": "expert_digest",
            "expert_scope": "group",
            "expert_group": "tech_business",
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )

    assert payload["query"] == query
    _assert_expert_digest_contract(
        payload,
        expected_experts=TECH_BUSINESS_EXPERTS,
        expected_expert_scope="group",
        expected_expert_group="tech_business",
        min_experts_with_sources=4,
    )
    _assert_no_retrieval_parser_failure_warnings(payload)
    assert response_bytes < 1_200_000


def test_production_expert_digest_recent_only_keeps_selection_explicit(
    production_token: str,
):
    query = (
        "Что сейчас полезно знать про кеширование при использовании LLM: "
        "prompt cache, context reuse, latency, стоимость и риски устаревания?"
    )

    payload, response_bytes = _post_agent_context(
        production_token,
        {
            "query": query,
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "akimov"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_recent_only": True,
            "use_super_passport": True,
        },
    )

    assert payload["selection_used"]["use_recent_only"] is True
    _assert_expert_digest_contract(
        payload,
        expected_experts=["refat", "akimov"],
        min_experts_with_sources=1,
    )
    _assert_no_retrieval_parser_failure_warnings(payload)
    assert response_bytes < 400_000


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


def test_production_expert_digest_is_bounded_and_raw_free_for_same_scope(
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
    for expert in source_payload["experts"]:
        for source in expert["main_sources"]:
            _assert_evidence_quality(source["evidence_quality"])
    assert all(expert["main_sources"] == [] for expert in digest_payload["experts"])
    assert digest_bytes < max(250_000, int(source_bytes * 1.5))
    assert "comment_id" not in json.dumps(digest_payload, ensure_ascii=False)


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
            assert source_ref["evidence_quality"]["comment_signal"] == "none"
    assert response_bytes < 300_000


def test_production_source_expand_caps_multiple_digest_sources_without_new_digest(
    production_token: str,
):
    digest_payload, _ = _post_agent_context(
        production_token,
        {
            "query": (
                "Какие источники лучше раскрывать после краткого digest, "
                "если нужно проверить нюансы про AI-workflow?"
            ),
            "response_mode": "expert_digest",
            "expert_scope": "custom",
            "expert_filter": ["refat", "doronin"],
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "include_reddit": False,
            "synthesis_level": "none",
            "use_super_passport": True,
        },
    )
    _assert_expert_digest_contract(
        digest_payload,
        expected_experts=["refat", "doronin"],
        min_experts_with_sources=1,
    )
    source_keys = _first_source_key_per_expert(digest_payload)[:2]
    assert source_keys

    expand_payload = _post_source_expand(
        production_token,
        {
            "source_keys": source_keys,
            "include_comments": True,
            "include_external_links": True,
            "max_content_chars": 240,
            "max_comments_per_source": 1,
        },
    )

    assert expand_payload["mode"] == "source_expand"
    assert expand_payload["not_found"] == []
    assert expand_payload["warnings"] == []
    assert len(expand_payload["sources"]) == len(source_keys)
    for source in expand_payload["sources"]:
        assert source["source_key"] in source_keys
        assert source["content"] is None or len(source["content"]) <= 240
        comments = source["comments"]
        comment_count = len(comments["author_comments"]) + len(
            comments["community_comments"]
        )
        assert comment_count <= 1
        assert set(source["truncation"]) == {
            "content_truncated",
            "comments_truncated",
        }
        _assert_evidence_quality(source["evidence_quality"])
        assert source["external_links"] == [] or all(
            link["fetch_status"] == "not_fetched"
            for link in source["external_links"]
        )


def test_production_source_expand_reveals_exact_source_with_evidence_quality(
    production_token: str,
):
    digest_payload, _ = _post_agent_context(
        production_token,
        {
            "query": "Как понять, что источник по AI-workflow сильный, а не просто анонс?",
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
        digest_payload,
        expected_experts=["refat", "akimov"],
        min_experts_with_sources=1,
    )
    source_key = next(
        source_ref["source_key"]
        for expert in digest_payload["experts"]
        for source_ref in expert["digest"]["source_refs"]
    )

    expand_payload = _post_source_expand(
        production_token,
        {
            "source_keys": [source_key],
            "include_comments": True,
            "include_external_links": True,
            "max_content_chars": 1600,
            "max_comments_per_source": 4,
        },
    )

    assert expand_payload["mode"] == "source_expand"
    assert expand_payload["not_found"] == []
    assert expand_payload["warnings"] == []
    assert len(expand_payload["sources"]) == 1
    source = expand_payload["sources"][0]
    assert source["source_key"] == source_key
    assert source["content"]
    assert "evidence_quality" in source
    _assert_evidence_quality(source["evidence_quality"])
    assert source["external_links"] == [] or all(
        link["fetch_status"] == "not_fetched"
        for link in source["external_links"]
    )


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


def test_production_source_expand_rejects_human_but_invalid_source_handle(
    production_token: str,
):
    response = requests.post(
        PRODUCTION_EXPAND_API_URL,
        headers={"Authorization": f"Bearer {production_token}"},
        json={
            "source_keys": ["рефат вот тот пост про subagents"],
            "include_comments": True,
            "include_external_links": True,
        },
        timeout=PRODUCTION_TIMEOUT_SECONDS,
    )

    assert response.status_code == 400, response.text[:1000]
    assert "<expert_id>:<telegram_message_id>" in response.text


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


def _post_source_expand(
    token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = requests.post(
        PRODUCTION_EXPAND_API_URL,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=PRODUCTION_TIMEOUT_SECONDS,
    )
    assert response.status_code == 200, response.text[:2000]
    return response.json()


def _assert_expert_digest_contract(
    payload: dict[str, Any],
    *,
    expected_experts: list[str],
    min_experts_with_sources: int,
    expected_expert_scope: str = "custom",
    expected_expert_group: str | None = None,
    include_main_source_comments: bool = True,
) -> None:
    assert payload["mode"] == "expert_digest"
    assert payload["selection_used"]["expert_scope"] == expected_expert_scope
    assert payload["selection_used"].get("expert_group") == expected_expert_group
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
        assert isinstance(digest.get("source_index"), list)
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
        max_source_refs = int((digest.get("limits_used") or {}).get("max_source_refs") or 0)
        if max_source_refs > 0:
            assert len(source_refs) <= max_source_refs
        assert digest["key_signals"]
        assert digest.get("position")
        assert digest["source_index"]

        for source_ref in source_refs:
            assert source_ref["source_key"].startswith(f"{expert['expert_id']}:")
            assert source_ref["relevance"] in {"HIGH", "MEDIUM"}
            assert source_ref.get("short_excerpt")
            max_source_chars = int(
                (digest.get("limits_used") or {}).get("max_source_chars") or 0
            )
            if max_source_chars > 0:
                assert len(source_ref["short_excerpt"]) <= max_source_chars + 50
            assert "evidence_quality" in source_ref
            _assert_evidence_quality(source_ref["evidence_quality"])
            for external_link in source_ref.get("external_links") or []:
                assert external_link["fetch_status"] == "not_fetched"

        for source_index_entry in digest["source_index"]:
            assert source_index_entry["source_key"].startswith(f"{expert['expert_id']}:")
            assert "evidence_quality" in source_index_entry
            _assert_evidence_quality(source_index_entry["evidence_quality"])

        for signal in digest["key_signals"]:
            assert signal["claim"]
            assert signal["support_level"] in SUPPORT_LEVELS
            assert set(signal.get("supporting_sources") or []).issubset(source_keys)

    assert experts_with_sources >= min_experts_with_sources


def _first_source_key_per_expert(payload: dict[str, Any]) -> list[str]:
    source_keys = []
    for expert in payload["experts"]:
        source_refs = expert["digest"]["source_refs"]
        if source_refs:
            source_keys.append(source_refs[0]["source_key"])
    return source_keys


def _assert_no_retrieval_parser_failure_warnings(payload: dict[str, Any]) -> None:
    warning_text = json.dumps(payload.get("warnings", []), ensure_ascii=False).lower()
    fatal_fragments = [
        "no such column",
        "syntax error",
        "fts5",
        "source_bundle_failed",
        "query_embedding_failed",
        "hybrid_retrieval_failed",
    ]
    assert not any(fragment in warning_text for fragment in fatal_fragments)


def _assert_evidence_quality(quality: dict[str, Any]) -> None:
    assert quality["depth"] in EVIDENCE_DEPTHS
    assert quality["source_type"] in EVIDENCE_SOURCE_TYPES
    assert quality["comment_signal"] in EVIDENCE_COMMENT_SIGNALS
    assert quality["confidence"] in EVIDENCE_CONFIDENCES
    assert isinstance(quality.get("notes"), list)
