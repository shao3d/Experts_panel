#!/usr/bin/env python3
"""BDD-style tests for the Agent Context API CLI wrapper."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.cli import agent_context, agent_context_expand


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


def _source_bundle_response():
    return {
        "request_id": "req_test",
        "mode": "source_bundle",
        "query": "AI agents for sales",
        "selection_used": {
            "expert_scope": "custom",
            "expert_group": None,
            "expert_filter": ["refat"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_recent_only": False,
            "use_super_passport": True,
        },
        "experts": [
            {
                "expert_id": "refat",
                "expert_name": "Refat",
                "channel_username": "nobilix",
                "selected_sources_count": 1,
                "unattached_linked_context": [
                    {"telegram_message_id": 202, "source_key": "refat:202"}
                ],
                "main_sources": [
                    {
                        "telegram_message_id": 101,
                        "source_key": "refat:101",
                        "relevance": "HIGH",
                        "reason": "Direct match",
                        "external_links": [
                            {
                                "url": "https://github.com/langchain-ai/langgraph",
                                "domain": "github.com",
                                "label": "LangGraph",
                                "context": "Direct match references LangGraph",
                                "link_type": "github_repo",
                                "fetch_status": "not_fetched",
                            }
                        ],
                        "linked_context": [
                            {"telegram_message_id": 201, "source_key": "refat:201"}
                        ],
                        "comments": {
                            "author_comments": [{"comment_id": 1}],
                            "community_comments": [{"comment_id": 2}],
                        },
                        "evidence_quality": {
                            "depth": "moderate",
                            "source_type": "analysis",
                            "comment_signal": "mixed",
                            "confidence": "medium",
                            "notes": ["direct comments are attached"],
                        },
                    }
                ],
                "no_results_reason": None,
            }
        ],
        "reddit": None,
        "pipeline_used": ["expert_selection", "source_selection"],
        "pipeline_skipped": ["reduce_answer_synthesis"],
        "warnings": ["refat:202: linked_context_without_provenance"],
        "processing_time_ms": 42,
    }


def _expert_digest_response():
    return {
        "request_id": "req_digest",
        "mode": "expert_digest",
        "query": "When should we use subagents?",
        "selection_used": {
            "expert_scope": "custom",
            "expert_group": None,
            "expert_filter": ["refat"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_recent_only": False,
            "use_super_passport": True,
        },
        "experts": [
            {
                "expert_id": "refat",
                "expert_name": "Refat",
                "channel_username": "nobilix",
                "selected_sources_count": 3,
                "unattached_linked_context": [],
                "main_sources": [],
                "digest": {
                    "position": "Use subagents for explicit bounded research.",
                    "key_signals": [
                        {
                            "claim": "Subagents help when the task has a clear scope.",
                            "support_level": "direct",
                            "supporting_sources": ["refat:101"],
                            "comment_signal": None,
                            "limits": None,
                        }
                    ],
                    "source_refs": [
                        {
                            "telegram_message_id": 101,
                            "source_key": "refat:101",
                            "relevance": "HIGH",
                            "reason": "Direct match",
                            "short_excerpt": "Compact source excerpt",
                            "created_at": "2026-04-10T12:00:00",
                            "external_links": [
                                {
                                    "url": "https://github.com/example/agent-tool",
                                    "domain": "github.com",
                                    "label": None,
                                    "context": None,
                                    "link_type": "github_repo",
                                    "fetch_status": "not_fetched",
                                }
                            ],
                            "linked_context_count": 1,
                            "author_comments_count": 1,
                            "community_comments_count": 1,
                            "evidence_quality": {
                                "depth": "deep_practical",
                                "source_type": "practitioner_experience",
                                "comment_signal": "mixed",
                                "confidence": "high",
                                "notes": ["source has practical detail"],
                            },
                        }
                    ],
                    "source_index": [
                        {
                            "telegram_message_id": 101,
                            "source_key": "refat:101",
                            "relevance": "HIGH",
                            "reason": "Direct match",
                            "created_at": "2026-04-10T12:00:00",
                            "author_comments_count": 1,
                            "community_comments_count": 1,
                            "external_links_count": 1,
                            "linked_context_count": 1,
                            "content_chars": 123,
                            "evidence_quality": {
                                "depth": "deep_practical",
                                "source_type": "practitioner_experience",
                                "comment_signal": "mixed",
                                "confidence": "high",
                                "notes": ["source has practical detail"],
                            },
                        },
                        {
                            "telegram_message_id": 102,
                            "source_key": "refat:102",
                            "relevance": "MEDIUM",
                            "reason": "Secondary match",
                            "created_at": "2026-04-09T12:00:00",
                            "author_comments_count": 0,
                            "community_comments_count": 0,
                            "external_links_count": 0,
                            "linked_context_count": 0,
                            "content_chars": 88,
                            "evidence_quality": {
                                "depth": "shallow",
                                "source_type": "mention",
                                "comment_signal": "none",
                                "confidence": "low",
                                "notes": ["short source"],
                            },
                        },
                    ],
                    "comments_digest": {
                        "author_comments_count": 1,
                        "community_comments_count": 1,
                        "included_comments": [
                            {
                                "source_key": "refat:101",
                                "comment_role": "author",
                                "author_name": "Refat",
                                "short_excerpt": "Author clarification",
                                "created_at": "2026-04-10T15:00:00",
                            }
                        ],
                        "omitted_comments_count": 1,
                    },
                    "omitted_counts": {
                        "main_sources": 2,
                        "linked_context": 0,
                        "author_comments": 0,
                        "community_comments": 1,
                        "external_links": 0,
                    },
                    "limits": ["Compact digest"],
                    "no_signal_reason": None,
                },
                "no_results_reason": None,
            }
        ],
        "reddit": None,
        "pipeline_used": ["expert_selection", "source_selection", "expert_digest_reduce"],
        "pipeline_skipped": ["reduce_answer_synthesis"],
        "warnings": [],
        "processing_time_ms": 42,
    }


def _source_expand_response():
    return {
        "request_id": "req_expand",
        "mode": "source_expand",
        "sources": [
            {
                "source_key": "refat:101",
                "expert_id": "refat",
                "expert_name": "Refat",
                "channel_username": "nobilix",
                "telegram_message_id": 101,
                "content": "Expanded raw source content",
                "created_at": "2026-04-10T12:00:00",
                "author_name": "Refat",
                "comments": {
                    "author_comments": [
                        {"comment_id": 1, "comment_text": "Author comment"}
                    ],
                    "community_comments": [
                        {"comment_id": 2, "comment_text": "Community comment"}
                    ],
                },
                "external_links": [
                    {
                        "url": "https://github.com/example/repo",
                        "domain": "github.com",
                        "label": None,
                        "context": "Expanded raw source content",
                        "link_type": "github_repo",
                        "fetch_status": "not_fetched",
                    }
                ],
                "truncation": {
                    "content_truncated": False,
                    "comments_truncated": False,
                },
                "evidence_quality": {
                    "depth": "moderate",
                    "source_type": "analysis",
                    "comment_signal": "mixed",
                    "confidence": "medium",
                    "notes": ["direct comments are attached"],
                },
            }
        ],
        "not_found": [],
        "warnings": [],
        "processing_time_ms": 12,
    }


@pytest.fixture
def clean_agent_context_env(monkeypatch):
    for key in [
        "AGENT_CONTEXT_API_TOKEN",
        "AGENT_CONTEXT_API_URL",
        "AGENT_CONTEXT_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_cli_missing_token_fails_before_http_call(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    def fail_post(*args, **kwargs):
        raise AssertionError("CLI should not call HTTP without a token")

    monkeypatch.setattr(agent_context.requests, "post", fail_post)

    exit_code = agent_context.main(
        ["--query", "AI agents for sales"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "AGENT_CONTEXT_API_TOKEN is required" in captured.err


def test_cli_sends_safe_default_source_bundle_payload(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    calls = []
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setenv(
        "AGENT_CONTEXT_API_URL",
        "http://example.test/api/v1/agent/context",
    )
    monkeypatch.setenv("AGENT_CONTEXT_TIMEOUT_SECONDS", "12")

    def fake_post(url, *, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(payload=_source_bundle_response())

    monkeypatch.setattr(agent_context.requests, "post", fake_post)

    exit_code = agent_context.main(
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "refat, akimov,refat",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["url"] == "http://example.test/api/v1/agent/context"
    assert calls[0]["headers"] == {"Authorization": "Bearer secret-token"}
    assert calls[0]["timeout"] == 12.0
    assert calls[0]["json"] == {
        "query": "AI agents for sales",
        "response_mode": "source_bundle",
        "expert_scope": "custom",
        "expert_group": None,
        "expert_filter": ["refat", "akimov"],
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": False,
        "use_super_passport": True,
    }
    assert "secret-token" not in captured.out
    assert "secret-token" not in captured.err


def test_cli_sends_expert_digest_payload_when_requested(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    calls = []
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def fake_post(url, *, headers, json, timeout):
        calls.append(json)
        return FakeResponse(payload=_expert_digest_response())

    monkeypatch.setattr(agent_context.requests, "post", fake_post)

    exit_code = agent_context.main(
        [
            "--query",
            "When should we use subagents?",
            "--experts",
            "refat",
            "--response-mode",
            "expert_digest",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls[0]["response_mode"] == "expert_digest"
    assert "Agent Context expert_digest" in captured.out
    assert "position: Use subagents for explicit bounded research." in captured.out
    assert "source_refs: 1" in captured.out
    assert "source_index: 2" in captured.out
    assert "refat:101 [HIGH] Direct match" in captured.out
    assert "quality: deep_practical/practitioner_experience; comments=mixed; confidence=high" in captured.out
    assert "[direct] Subagents help when the task has a clear scope." in captured.out
    assert "comments_digest: author=1 community=1 included=1 omitted=1" in captured.out
    assert "omitted_counts" in captured.out


def test_expand_cli_sends_source_keys_payload(monkeypatch, capsys, clean_agent_context_env):
    calls = []

    def fake_post(url, *, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(payload=_source_expand_response())

    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "token")
    monkeypatch.setattr(agent_context_expand.requests, "post", fake_post)

    exit_code = agent_context_expand.main(
        [
            "--source-keys",
            "refat:101,etechlead:139",
            "--max-content-chars",
            "1234",
            "--max-comments-per-source",
            "7",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls[0]["url"] == "http://localhost:8000/api/v1/agent/context/expand"
    assert calls[0]["json"] == {
        "source_keys": ["refat:101", "etechlead:139"],
        "include_comments": True,
        "include_external_links": True,
        "max_content_chars": 1234,
        "max_comments_per_source": 7,
    }
    assert "Agent Context source_expand" in captured.out
    assert "refat:101 (@nobilix)" in captured.out
    assert "quality: moderate/analysis; comments=mixed; confidence=medium" in captured.out
    assert "comments: author=1 community=1" in captured.out
    assert "external_links=1" in captured.out


def test_expand_cli_missing_token_fails_before_http_call(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    def fail_post(*args, **kwargs):
        raise AssertionError("Expand CLI should not call HTTP without a token")

    monkeypatch.setattr(agent_context_expand.requests, "post", fail_post)

    exit_code = agent_context_expand.main(
        ["--source-keys", "refat:101"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "AGENT_CONTEXT_API_TOKEN is required" in captured.err


def test_expand_cli_module_entrypoint_runs_before_http_call(clean_agent_context_env):
    env = os.environ.copy()
    env["AGENT_CONTEXT_API_TOKEN"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.agent_context_expand",
            "--source-keys",
            "refat:101",
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "AGENT_CONTEXT_API_TOKEN is required" in result.stderr


def test_cli_default_timeout_matches_live_source_bundle_budget(
    monkeypatch,
    clean_agent_context_env,
):
    calls = []
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def fake_post(url, *, headers, json, timeout):
        calls.append(timeout)
        return FakeResponse(payload=_source_bundle_response())

    monkeypatch.setattr(agent_context.requests, "post", fake_post)

    exit_code = agent_context.main(
        ["--query", "AI agents for sales", "--experts", "refat,akimov"],
        load_env=False,
    )

    assert exit_code == 0
    assert calls == [3600.0]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["--query", "AI agents"],
            {"expert_scope": "all", "expert_group": None, "expert_filter": None},
        ),
        (
            ["--query", "AI agents", "--group", "tech"],
            {"expert_scope": "group", "expert_group": "tech", "expert_filter": None},
        ),
        (
            ["--query", "AI agents", "--experts", "refat,akimov", "--recent"],
            {
                "expert_scope": "custom",
                "expert_group": None,
                "expert_filter": ["refat", "akimov"],
                "use_recent_only": True,
            },
        ),
    ],
)
def test_cli_supports_all_group_and_custom_selection(
    monkeypatch,
    clean_agent_context_env,
    argv,
    expected,
):
    calls = []
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def fake_post(url, *, headers, json, timeout):
        calls.append(json)
        return FakeResponse(payload=_source_bundle_response())

    monkeypatch.setattr(agent_context.requests, "post", fake_post)

    exit_code = agent_context.main(argv, load_env=False)

    assert exit_code == 0
    for key, value in expected.items():
        assert calls[0][key] == value


def test_cli_prints_agent_readable_source_bundle_summary(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setattr(
        agent_context.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(payload=_source_bundle_response()),
    )

    exit_code = agent_context.main(
        ["--query", "AI agents", "--experts", "refat"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "selection_used" in captured.out
    assert "expert_scope: custom" in captured.out
    assert "warnings" in captured.out
    assert "refat" in captured.out
    assert "selected_sources_count: 1" in captured.out
    assert "101 [HIGH] Direct match" in captured.out
    assert "quality: moderate/analysis; comments=mixed; confidence=medium" in captured.out
    assert "comments: author=1 community=1" in captured.out
    assert "linked_context=1" in captured.out
    assert "external_links=1" in captured.out
    assert "unattached_linked_context: 1" in captured.out


def test_cli_json_mode_prints_raw_api_json(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    payload = _source_bundle_response()
    monkeypatch.setattr(
        agent_context.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(payload=payload),
    )

    exit_code = agent_context.main(
        ["--query", "AI agents", "--experts", "refat", "--json"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == payload


def test_cli_http_error_exits_nonzero_with_api_message(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setattr(
        agent_context.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            status_code=501,
            payload={"message": "include_reddit is not implemented"},
        ),
    )

    exit_code = agent_context.main(
        ["--query", "AI agents", "--experts", "refat"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "include_reddit is not implemented" in captured.err


def test_cli_timeout_exits_nonzero_with_actionable_message(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def timeout_post(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(agent_context.requests, "post", timeout_post)

    exit_code = agent_context.main(
        ["--query", "AI agents", "--experts", "refat"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "timed out" in captured.err
