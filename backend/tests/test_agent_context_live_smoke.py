#!/usr/bin/env python3
"""BDD tests for the Agent Context live local smoke helper."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts import agent_context_live_smoke as live_smoke

CLAUDE_AGENT_PATH = BACKEND_DIR.parent / ".claude" / "agents" / "experts_panel_researcher.md"
CODEX_AGENT_PATH = BACKEND_DIR.parent / ".codex" / "agents" / "experts_panel_researcher.toml"
SPEC_PATH = BACKEND_DIR.parent / "docs" / "architecture" / "agent-context-api.md"


def _passed_payload():
    return {
        "request_id": "req_live_smoke",
        "mode": "source_bundle",
        "query": "AI agents for sales",
        "selection_used": {
            "expert_scope": "custom",
            "expert_group": None,
            "expert_filter": ["refat", "akimov"],
            "include_reddit": False,
            "include_main_source_comments": True,
            "include_drift_comment_groups": False,
            "synthesis_level": "none",
            "use_recent_only": False,
        },
        "experts": [
            {
                "expert_id": "refat",
                "selected_sources_count": 2,
                "main_sources": [{"telegram_message_id": 101}],
                "unattached_linked_context": [],
                "no_results_reason": None,
            },
            {
                "expert_id": "akimov",
                "selected_sources_count": 1,
                "main_sources": [{"telegram_message_id": 201}],
                "unattached_linked_context": [],
                "no_results_reason": None,
            },
        ],
        "reddit": None,
        "pipeline_used": ["expert_selection", "source_selection"],
        "pipeline_skipped": [
            "reduce_answer_synthesis",
            "cross_expert_meta_synthesis",
        ],
        "warnings": ["live_smoke: synthetic test payload"],
        "processing_time_ms": 42,
    }


def test_missing_token_is_skipped_by_default(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.delenv("AGENT_CONTEXT_API_TOKEN", raising=False)

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    assert exit_code == 0
    assert report["status"] == "skipped"
    assert report["reason"] == "missing_agent_context_api_token"
    assert "AGENT_CONTEXT_API_TOKEN" in report["message"]
    assert "Bearer" not in json.dumps(report)


def test_require_live_turns_missing_token_into_failure(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.delenv("AGENT_CONTEXT_API_TOKEN", raising=False)

    exit_code = live_smoke.main(
        ["--report-path", str(report_path), "--require-live"]
    )

    report = json.loads(report_path.read_text())
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "missing_agent_context_api_token"


def test_live_smoke_uses_free_port_and_explicit_api_url(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    observed = {}
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54321)

    class FakeProcess:
        def __init__(self):
            self.returncode = None

        def poll(self):
            return None

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    def fake_start_backend(port):
        observed["port"] = port
        return FakeProcess()

    def fake_wait_for_health(base_url, timeout_seconds):
        observed["health_url"] = base_url
        return True

    def fake_run_cli(*, query, experts, api_url, timeout_seconds):
        observed["query"] = query
        observed["experts"] = experts
        observed["api_url"] = api_url
        observed["timeout_seconds"] = timeout_seconds
        return SimpleNamespace(returncode=0, stdout=json.dumps(_passed_payload()), stderr="")

    monkeypatch.setattr(live_smoke, "_start_backend", fake_start_backend)
    monkeypatch.setattr(live_smoke, "_wait_for_health", fake_wait_for_health)
    monkeypatch.setattr(live_smoke, "_run_cli", fake_run_cli)

    exit_code = live_smoke.main(
        [
            "--report-path",
            str(report_path),
            "--query",
            "AI agents for sales",
            "--experts",
            "refat,akimov",
        ]
    )

    report = json.loads(report_path.read_text())
    assert exit_code == 0
    assert observed["port"] == 54321
    assert observed["health_url"] == "http://127.0.0.1:54321"
    assert observed["api_url"] == "http://127.0.0.1:54321/api/v1/agent/context"
    assert observed["timeout_seconds"] == 3600.0
    assert report["status"] == "passed"
    assert report["api_url"] == "http://127.0.0.1:54321/api/v1/agent/context"
    assert "secret-live-token" not in json.dumps(report)


def test_successful_smoke_sanitizes_report(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54322)
    monkeypatch.setattr(live_smoke, "_start_backend", lambda port: None)
    monkeypatch.setattr(live_smoke, "_wait_for_health", lambda base_url, timeout_seconds: True)
    monkeypatch.setattr(
        live_smoke,
        "_run_cli",
        lambda **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(_passed_payload()),
            stderr="",
        ),
    )

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    serialized = json.dumps(report)
    assert exit_code == 0
    assert report["status"] == "passed"
    assert report["query"] == "AI agents for sales"
    assert report["experts"] == ["refat", "akimov"]
    assert report["selected_source_counts"] == {"refat": 2, "akimov": 1}
    assert report["response_bytes"] > 0
    assert report["warnings"] == ["live_smoke: synthetic test payload"]
    assert "reduce_answer_synthesis" in report["pipeline_skipped"]
    assert "Authorization" not in serialized
    assert "Bearer" not in serialized
    assert "secret-live-token" not in serialized


def test_non_source_bundle_response_is_actionable_failure(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54323)
    monkeypatch.setattr(live_smoke, "_start_backend", lambda port: None)
    monkeypatch.setattr(live_smoke, "_wait_for_health", lambda base_url, timeout_seconds: True)
    monkeypatch.setattr(
        live_smoke,
        "_run_cli",
        lambda **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"mode": "answer", "experts": []}),
            stderr="",
        ),
    )

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "invalid_source_bundle_response"
    assert "source_bundle" in report["message"]


def test_cli_failure_is_sanitized_actionable_failure(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54324)
    monkeypatch.setattr(live_smoke, "_start_backend", lambda port: None)
    monkeypatch.setattr(live_smoke, "_wait_for_health", lambda base_url, timeout_seconds: True)
    monkeypatch.setattr(
        live_smoke,
        "_run_cli",
        lambda **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Error: Bearer secret-live-token failed",
        ),
    )

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    serialized = json.dumps(report)
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "cli_failed"
    assert "secret-live-token" not in serialized
    assert "Bearer" not in serialized


def test_response_size_cap_failure_is_classified_actionably(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54325)
    monkeypatch.setattr(live_smoke, "_start_backend", lambda port: None)
    monkeypatch.setattr(live_smoke, "_wait_for_health", lambda base_url, timeout_seconds: True)
    monkeypatch.setattr(
        live_smoke,
        "_run_cli",
        lambda **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=(
                "Error: Agent Context API returned HTTP 413: "
                "Agent Context API response exceeds configured max bytes\n"
            ),
        ),
    )

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    serialized = json.dumps(report)
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "response_too_large"
    assert "response-size cap" in report["message"]
    assert "HTTP 413" in report["error"]
    assert "secret-live-token" not in serialized
    assert "Bearer" not in serialized


def test_api_timeout_failure_is_classified_actionably(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54326)
    monkeypatch.setattr(live_smoke, "_start_backend", lambda port: None)
    monkeypatch.setattr(live_smoke, "_wait_for_health", lambda base_url, timeout_seconds: True)
    monkeypatch.setattr(
        live_smoke,
        "_run_cli",
        lambda **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=(
                "Error: Agent Context API returned HTTP 504: "
                "Agent Context API request exceeded configured timeout\n"
            ),
        ),
    )

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    serialized = json.dumps(report)
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "api_timeout"
    assert "timeout" in report["message"]
    assert "HTTP 504" in report["error"]
    assert "secret-live-token" not in serialized
    assert "Bearer" not in serialized


def test_cli_subprocess_timeout_writes_sanitized_report(tmp_path, monkeypatch):
    report_path = tmp_path / "latest.json"
    monkeypatch.setattr(live_smoke, "load_backend_env", lambda path: path)
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", "secret-live-token")
    monkeypatch.setattr(live_smoke, "_find_free_port", lambda: 54327)
    monkeypatch.setattr(live_smoke, "_start_backend", lambda port: None)
    monkeypatch.setattr(live_smoke, "_wait_for_health", lambda base_url, timeout_seconds: True)

    def timeout_run(**kwargs):
        raise live_smoke.subprocess.TimeoutExpired(
            cmd=["agent_context", "Bearer", "secret-live-token"],
            timeout=3600,
        )

    monkeypatch.setattr(live_smoke, "_run_cli", timeout_run)

    exit_code = live_smoke.main(["--report-path", str(report_path)])

    report = json.loads(report_path.read_text())
    serialized = json.dumps(report)
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "cli_timeout"
    assert "subprocess exceeded" in report["message"]
    assert "secret-live-token" not in serialized
    assert "Bearer" not in serialized


def test_live_smoke_command_and_statuses_are_documented():
    with CODEX_AGENT_PATH.open("rb") as handle:
        codex_instructions = __import__("tomllib").load(handle)["developer_instructions"]
    combined = "\n".join(
        [
            CLAUDE_AGENT_PATH.read_text(encoding="utf-8"),
            codex_instructions,
            SPEC_PATH.read_text(encoding="utf-8"),
        ]
    )
    normalized = " ".join(combined.lower().split())

    assert "scripts/agent_context_live_smoke.py" in combined
    assert "--require-live" in combined
    assert "passed" in normalized
    assert "skipped" in normalized
    assert "failed" in normalized
    assert "backend/test_results/agent_context_live_smoke/latest.json" in combined
    assert "production fly" in normalized
    assert "not" in normalized
