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

from src.cli import agent_context, agent_context_expand, panex


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
                            "short_excerpt": "Source excerpt",
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
                    "limits_used": {
                        "max_source_refs": 0,
                        "max_source_chars": 0,
                        "max_comments_per_source": 0,
                        "max_comment_chars": 0,
                        "max_links_per_source": 0,
                        "max_signals": 0,
                        "source_index_scope": "all_selected_sources",
                    },
                    "limits": ["Backend digest"],
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


def _large_expert_digest_response():
    payload = _expert_digest_response()
    payload["request_id"] = "req_large_digest"
    payload["experts"] = [
        {
            **payload["experts"][0],
            "expert_id": "refat",
            "expert_name": "Refat",
        },
        {
            **payload["experts"][0],
            "expert_id": "akimov",
            "expert_name": "Akimov",
            "channel_username": "ai_product",
            "digest": {
                **payload["experts"][0]["digest"],
                "position": "AI should be tied to a concrete product workflow.",
                "key_signals": [
                    {
                        "claim": "AI helps when it is tied to a concrete workflow.",
                        "support_level": "direct",
                        "supporting_sources": ["akimov:201"],
                        "comment_signal": None,
                        "limits": None,
                    }
                ],
                "source_refs": [
                    {
                        **payload["experts"][0]["digest"]["source_refs"][0],
                        "telegram_message_id": 201,
                        "source_key": "akimov:201",
                        "short_excerpt": "Product workflow excerpt " * 800,
                    }
                ],
                "source_index": [
                    {
                        **payload["experts"][0]["digest"]["source_index"][0],
                        "telegram_message_id": 201,
                        "source_key": "akimov:201",
                    }
                ],
                "comments_digest": {
                    **payload["experts"][0]["digest"]["comments_digest"],
                    "included_comments": [
                        {
                            "source_key": "akimov:201",
                            "comment_role": "author",
                            "author_name": "Akimov",
                            "short_excerpt": "Author clarification",
                            "created_at": "2026-04-10T15:00:00",
                        }
                    ],
                },
            },
        },
    ]
    payload["experts"][0]["digest"]["source_refs"][0]["short_excerpt"] = (
        "Bounded subagent excerpt " * 800
    )
    return payload


def _source_expand_response(limits_used=None):
    return {
        "request_id": "req_expand",
        "mode": "source_expand",
        "limits_used": limits_used
        or {
            "include_comments": True,
            "include_external_links": True,
            "max_content_chars": 20000,
            "max_comments_per_source": 50,
        },
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


def _source_expand_limits_from_request(request_payload):
    return {
        "include_comments": request_payload["include_comments"],
        "include_external_links": request_payload["include_external_links"],
        "max_content_chars": request_payload["max_content_chars"],
        "max_comments_per_source": request_payload["max_comments_per_source"],
    }


@pytest.fixture
def clean_agent_context_env(monkeypatch):
    for key in [
        "AGENT_CONTEXT_API_TOKEN",
        "AGENT_CONTEXT_API_URL",
        "AGENT_CONTEXT_EXPAND_API_URL",
        "AGENT_CONTEXT_TIMEOUT_SECONDS",
        "PANEX_ARTIFACT_DIR",
        "PANEX_ARTIFACT_TTL_DAYS",
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


def test_panex_ask_from_foreign_cwd_uses_fly_expert_digest_by_default(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setenv(
        "AGENT_CONTEXT_API_URL",
        "http://localhost:8000/api/v1/agent/context",
    )

    def fake_post(url, *, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(payload=_expert_digest_response())

    monkeypatch.setattr(panex.requests, "post", fake_post)

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "When should we use subagents?",
            "--experts",
            "refat,akimov,refat",
            "--json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls[0]["url"] == panex.PRODUCTION_AGENT_CONTEXT_API_URL
    assert "localhost" not in calls[0]["url"]
    assert calls[0]["headers"] == {"Authorization": "Bearer secret-token"}
    assert calls[0]["timeout"] == 3600.0
    assert calls[0]["json"] == {
        "query": "When should we use subagents?",
        "response_mode": "expert_digest",
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


def test_panex_ask_save_receipt_json_writes_full_artifact_without_stdout_dump(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    artifact_dir = tmp_path / "artifacts"
    payload = _large_expert_digest_response()
    foreign_repo = tmp_path / "foreign_repo"
    foreign_repo.mkdir()
    monkeypatch.chdir(foreign_repo)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setenv("PANEX_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setattr(
        panex.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(payload=payload),
    )

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "When should we use subagents?",
            "--experts",
            "refat,akimov",
            "--save",
            "--receipt-json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    receipt = json.loads(captured.out)
    assert receipt["kind"] == "panex_artifact"
    assert receipt["operation"] == "ask"
    assert receipt["request_id"] == "req_large_digest"
    assert receipt["mode"] == "expert_digest"
    assert receipt["artifact_path"].startswith(str(artifact_dir))
    assert receipt["response_bytes"] > 1000
    assert any(command.startswith("panex export --path ") for command in receipt["read_next"])
    assert "Bounded subagent excerpt" not in captured.out
    assert "secret-token" not in captured.out
    assert "secret-token" not in captured.err

    response_path = Path(receipt["artifact_path"])
    receipt_path = Path(receipt["receipt_path"])
    assert response_path.exists()
    assert receipt_path.exists()
    assert response_path.parent == receipt_path.parent
    assert not response_path.is_relative_to(Path.cwd())
    assert json.loads(response_path.read_text(encoding="utf-8")) == payload
    assert "secret-token" not in response_path.read_text(encoding="utf-8")
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt


def test_panex_ask_save_uses_stable_default_artifact_dir(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    default_root = tmp_path / "home" / panex.DEFAULT_ARTIFACT_ROOT_RELATIVE
    monkeypatch.setattr(panex, "_default_artifact_root", lambda: default_root)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setattr(
        panex.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(payload=_expert_digest_response()),
    )

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "When should we use subagents?",
            "--experts",
            "refat",
            "--save",
            "--receipt-json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    receipt = json.loads(captured.out)
    assert receipt["artifact_path"].startswith(str(default_root))
    assert Path(receipt["artifact_path"]).exists()


def test_panex_save_creates_unique_artifacts_for_repeated_calls(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setenv("PANEX_ARTIFACT_DIR", str(artifact_dir))
    calls = iter([
        FakeResponse(payload={**_expert_digest_response(), "request_id": "req_one"}),
        FakeResponse(payload={**_expert_digest_response(), "request_id": "req_two"}),
    ])
    monkeypatch.setattr(panex.requests, "post", lambda *args, **kwargs: next(calls))

    for _ in range(2):
        assert panex.main(
            [
                "ask",
                "--query",
                "When should we use subagents?",
                "--experts",
                "refat",
                "--save",
                "--receipt-json",
            ],
            load_env=False,
        ) == 0

    outputs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert outputs[0]["artifact_path"] != outputs[1]["artifact_path"]
    assert Path(outputs[0]["artifact_path"]).exists()
    assert Path(outputs[1]["artifact_path"]).exists()


def test_panex_expand_save_receipt_json_writes_source_expand_artifact(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    payload = _source_expand_response()
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setenv("PANEX_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        panex.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(payload=payload),
    )

    exit_code = panex.main(
        [
            "expand",
            "--source-keys",
            "refat:101",
            "--save",
            "--receipt-json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    receipt = json.loads(captured.out)
    assert receipt["operation"] == "expand"
    assert receipt["mode"] == "source_expand"
    assert receipt["source_keys"] == ["refat:101"]
    assert json.loads(Path(receipt["artifact_path"]).read_text(encoding="utf-8")) == payload


def test_panex_all_experts_requires_artifact_transport(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def fail_post(*args, **kwargs):
        raise AssertionError("all-experts request without artifact should fail before HTTP")

    monkeypatch.setattr(panex.requests, "post", fail_post)

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "wide query",
            "--all",
            "--json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "all-experts panex ask requires --save or --output" in captured.err


def test_panex_output_file_requires_overwrite_for_existing_file(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    output_path = tmp_path / "panex_raw.json"
    output_path.write_text("existing", encoding="utf-8")
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setattr(
        panex.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(payload=_expert_digest_response()),
    )

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "When should we use subagents?",
            "--experts",
            "refat",
            "--output",
            str(output_path),
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "already exists" in captured.err
    assert output_path.read_text(encoding="utf-8") == "existing"

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "When should we use subagents?",
            "--experts",
            "refat",
            "--output",
            str(output_path),
            "--overwrite",
            "--receipt-json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    receipt = json.loads(captured.out)
    assert receipt["artifact_path"] == str(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == _expert_digest_response()


def test_panex_read_manifest_expert_and_source_key_slices(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    artifact_path = tmp_path / "response.json"
    payload = _large_expert_digest_response()
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert panex.main(["read", "--path", str(artifact_path), "--manifest", "--json"], load_env=False) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["request_id"] == "req_large_digest"
    assert manifest["mode"] == "expert_digest"
    assert manifest["experts"] == ["refat", "akimov"]
    assert manifest["expert_count"] == 2
    assert manifest["response_bytes"] == artifact_path.stat().st_size

    assert panex.main(["read", "--path", str(artifact_path), "--expert", "akimov", "--json"], load_env=False) == 0
    expert_slice = json.loads(capsys.readouterr().out)
    assert expert_slice["expert_id"] == "akimov"
    assert "refat" not in json.dumps(expert_slice, ensure_ascii=False)

    assert panex.main(["read", "--path", str(artifact_path), "--source-key", "akimov:201", "--json"], load_env=False) == 0
    source_slice = json.loads(capsys.readouterr().out)
    assert source_slice["source_key"] == "akimov:201"


def test_panex_export_writes_human_files_without_raw_stdout(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    artifact_path = tmp_path / "response.json"
    out_dir = tmp_path / "exported"
    payload = _large_expert_digest_response()
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    exit_code = panex.main(
        [
            "export",
            "--path",
            str(artifact_path),
            "--out-dir",
            str(out_dir),
            "--json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    result = json.loads(captured.out)
    assert result["kind"] == "panex_artifact_export"
    assert result["artifact_path"] == str(artifact_path)
    assert result["output_dir"] == str(out_dir)
    assert result["status"] == "written"
    assert "Bounded subagent excerpt" not in captured.out

    manifest = json.loads(Path(result["files"]["manifest"]).read_text(encoding="utf-8"))
    digest_markdown = Path(result["files"]["digest_markdown"]).read_text(encoding="utf-8")
    sources_index = Path(result["files"]["sources_index_tsv"]).read_text(encoding="utf-8")

    assert manifest["mode"] == "expert_digest"
    assert manifest["source_keys_count"] == 3
    assert "# Panex Artifact Digest" in digest_markdown
    assert "refat:101" in digest_markdown
    assert "refat:102" in digest_markdown
    assert "akimov:201" in digest_markdown
    assert "source_key\texpert_id\ttelegram_message_id" in sources_index
    assert "refat:101\trefat\t101\tHIGH\t2026-04-10T12:00:00\tDirect match" in sources_index
    assert sources_index.count("refat:101") == 1
    assert "akimov:201\takimov\t201" in sources_index

    exit_code = panex.main(
        ["export", "--path", str(artifact_path), "--out-dir", str(out_dir), "--json"],
        load_env=False,
    )
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "existing"

    (out_dir / "sources_index.tsv").unlink()
    exit_code = panex.main(
        ["export", "--path", str(artifact_path), "--out-dir", str(out_dir)],
        load_env=False,
    )
    assert exit_code == 1
    assert "partial export already exists" in capsys.readouterr().err


def test_panex_cleanup_removes_only_old_artifacts(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    artifact_dir = tmp_path / "artifacts"
    old_dir = artifact_dir / "2026-04-01" / "old"
    fresh_dir = artifact_dir / "2026-05-07" / "fresh"
    tmp_dir = artifact_dir / "2026-04-01" / "writing.tmp"
    lock_dir = artifact_dir / "2026-04-01" / "locked"
    for directory in [old_dir, fresh_dir, tmp_dir, lock_dir]:
        directory.mkdir(parents=True)
        (directory / "response.json").write_text("{}", encoding="utf-8")
    (lock_dir / ".lock").write_text("", encoding="utf-8")

    old_timestamp = 1_700_000_000
    os.utime(old_dir, (old_timestamp, old_timestamp))
    os.utime(old_dir / "response.json", (old_timestamp, old_timestamp))
    os.utime(tmp_dir, (old_timestamp, old_timestamp))
    os.utime(lock_dir, (old_timestamp, old_timestamp))
    monkeypatch.setenv("PANEX_ARTIFACT_DIR", str(artifact_dir))

    exit_code = panex.main(["cleanup", "--ttl-days", "1", "--json"], load_env=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    result = json.loads(captured.out)
    assert result["deleted_count"] == 1
    assert not old_dir.exists()
    assert fresh_dir.exists()
    assert tmp_dir.exists()
    assert lock_dir.exists()


@pytest.mark.parametrize("command", ["guide", "help"])
def test_panex_guide_prints_human_usage_without_token_or_http(
    command,
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    def fail_post(*args, **kwargs):
        raise AssertionError("panex guide/help should not call HTTP")

    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "very-secret-token")
    monkeypatch.setattr(panex.requests, "post", fail_post)

    exit_code = panex.main([command], load_env=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Panex guide" in captured.out
    assert "panex ask" in captured.out
    assert "panex expand" in captured.out
    assert "panex export" in captured.out
    assert "panex doctor" in captured.out
    assert "expert_digest" in captured.out
    assert "source_bundle" in captured.out
    assert "drift comment groups" in captured.out
    assert "very-secret-token" not in captured.out
    assert "very-secret-token" not in captured.err


def test_panex_ask_keeps_source_bundle_opt_in_for_raw_audit(
    monkeypatch,
    tmp_path,
    clean_agent_context_env,
):
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def fake_post(url, *, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return FakeResponse(payload=_source_bundle_response())

    monkeypatch.setattr(panex.requests, "post", fake_post)

    exit_code = panex.main(
        [
            "ask",
            "--query",
            "raw audit",
            "--experts",
            "refat",
            "--response-mode",
            "source_bundle",
            "--json",
        ],
        load_env=False,
    )

    assert exit_code == 0
    assert calls == [
        {
            "url": panex.PRODUCTION_AGENT_CONTEXT_API_URL,
            "json": {
                "query": "raw audit",
                "response_mode": "source_bundle",
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
        }
    ]


def test_panex_expand_from_foreign_cwd_uses_fly_expand_by_default(
    monkeypatch,
    capsys,
    tmp_path,
    clean_agent_context_env,
):
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")
    monkeypatch.setenv(
        "AGENT_CONTEXT_EXPAND_API_URL",
        "http://localhost:8000/api/v1/agent/context/expand",
    )

    def fake_post(url, *, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            payload=_source_expand_response(
                limits_used=_source_expand_limits_from_request(json)
            )
        )

    monkeypatch.setattr(panex.requests, "post", fake_post)

    exit_code = panex.main(
        [
            "expand",
            "--source-keys",
            "refat:101,akimov:201",
            "--max-content-chars",
            "1200",
            "--max-comments-per-source",
            "3",
            "--json",
        ],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls[0]["url"] == panex.PRODUCTION_AGENT_CONTEXT_EXPAND_API_URL
    assert "localhost" not in calls[0]["url"]
    assert calls[0]["json"] == {
        "source_keys": ["refat:101", "akimov:201"],
        "include_comments": True,
        "include_external_links": True,
        "max_content_chars": 1200,
        "max_comments_per_source": 3,
    }
    assert "secret-token" not in captured.out
    assert "secret-token" not in captured.err


def test_panex_missing_token_fails_before_http_call(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    def fail_post(*args, **kwargs):
        raise AssertionError("panex should not call HTTP without token")

    monkeypatch.setattr(panex.requests, "post", fail_post)

    exit_code = panex.main(
        ["ask", "--query", "When should we use subagents?", "--experts", "refat"],
        load_env=False,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "AGENT_CONTEXT_API_TOKEN is required for panex production calls" in captured.err
    assert "secret" not in captured.err.lower()


def test_panex_local_debug_is_explicit(monkeypatch, clean_agent_context_env):
    calls = []
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-token")

    def fake_post(url, *, headers, json, timeout):
        calls.append(url)
        return FakeResponse(payload=_expert_digest_response())

    monkeypatch.setattr(panex.requests, "post", fake_post)

    exit_code = panex.main(
        ["ask", "--query", "debug", "--experts", "refat", "--local"],
        load_env=False,
    )

    assert exit_code == 0
    assert calls == [panex.LOCAL_AGENT_CONTEXT_API_URL]


def test_panex_doctor_reports_setup_without_printing_token(
    monkeypatch,
    capsys,
    clean_agent_context_env,
):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "very-secret-token")
    monkeypatch.setattr(panex.shutil, "which", lambda name: "/Users/me/.local/bin/panex")

    exit_code = panex.main(["doctor"], load_env=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Panex doctor" in captured.out
    assert "token_configured: True" in captured.out
    assert "very-secret-token" not in captured.out
    assert panex.PRODUCTION_AGENT_CONTEXT_API_URL in captured.out


def test_panex_install_script_writes_user_level_shim_without_token(tmp_path):
    install_dir = tmp_path / "bin"
    env = os.environ.copy()
    env["PANEX_INSTALL_DIR"] = str(install_dir)
    env["AGENT_CONTEXT_API_TOKEN"] = "very-secret-token"

    result = subprocess.run(
        [str(BACKEND_DIR.parent / "scripts" / "install_panex_runner.sh")],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    shim = install_dir / "panex"
    assert result.returncode == 0
    assert shim.exists()
    assert os.access(shim, os.X_OK)
    shim_content = shim.read_text(encoding="utf-8")
    assert "src.cli.panex" in shim_content
    assert str(BACKEND_DIR) in shim_content
    assert "very-secret-token" not in shim_content
    assert "very-secret-token" not in result.stdout
    assert "very-secret-token" not in result.stderr


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
    assert (
        "limits_used: source_refs=all; source_chars=all; comments/source=all; "
        "comment_chars=all; links/source=all; signals=all; "
        "source_index=all_selected_sources"
    ) in captured.out
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
        return FakeResponse(
            payload=_source_expand_response(
                limits_used=_source_expand_limits_from_request(json)
            )
        )

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
    assert (
        "limits_used: content_chars<=1234; comments/source<=7; "
        "include_comments=true; include_external_links=true"
    ) in captured.out
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
