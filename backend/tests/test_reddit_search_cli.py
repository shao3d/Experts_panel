#!/usr/bin/env python3
"""Contract tests for the reddit-search CLI (backend/src/cli/reddit_search.py).

Covers the handoff CLI requirements:

- completed → exit 0, human summary with sources
- abstained → exit 0, human message (NOT a technical error)
- technical error (5xx/timeout/unreachable/missing token) → exit 1
- --json → stable raw JSON, exit 0
- --doctor → health report, no token needed
- token never printed in output
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest
import requests

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.cli import reddit_search as cli


def _completed_payload():
    return {
        "status": "completed",
        "query": "hooks",
        "answer": "Practitioners say hooks are powerful.",
        "sources": [
            {"title": "Hooks workflow", "url": "https://reddit.com/r/ClaudeCode/comments/abc/hooks/", "subreddit": "ClaudeCode"}
        ],
        "message": None,
        "found_count": 1,
        "processing_time_ms": 1234,
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


# ---------------------------------------------------------------------------
# print_summary / exit codes
# ---------------------------------------------------------------------------


def test_completed_summary_exit_0(capsys):
    code = cli.print_summary(_completed_payload())
    out = capsys.readouterr().out
    assert code == 0
    assert "completed" in out
    assert "Practitioners say hooks are powerful." in out
    assert "r/ClaudeCode" in out
    assert "https://reddit.com/r/ClaudeCode" in out


def test_abstained_summary_exit_0(capsys):
    code = cli.print_summary({"status": "abstained", "message": "no reliable results"})
    out = capsys.readouterr().out
    assert code == 0
    assert "abstained" in out
    assert "no reliable results" in out


def test_unknown_status_exit_1(capsys):
    code = cli.print_summary({"status": "weird"})
    assert code == 1


# ---------------------------------------------------------------------------
# call_reddit_search
# ---------------------------------------------------------------------------


def test_missing_token_raises():
    with mock.patch.dict("os.environ", {}, clear=True):
        with pytest.raises(cli.RedditSearchCliError, match="AGENT_CONTEXT_API_TOKEN"):
            cli.call_reddit_search(cli.parse_args(["query text"]))


def test_completed_call(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs.get("json")
        calls["headers"] = kwargs.get("headers")
        return FakeResponse(200, _completed_payload())

    monkeypatch.setattr(cli.requests, "post", fake_post)
    with mock.patch.dict("os.environ", {"AGENT_CONTEXT_API_TOKEN": "tok123"}):
        payload = cli.call_reddit_search(cli.parse_args(["hooks", "--recent"]))

    assert calls["url"] == cli.DEFAULT_REDDIT_SEARCH_API_URL
    assert calls["json"] == {"query": "hooks", "use_recent_only": True}
    assert calls["headers"] == {"Authorization": "Bearer tok123"}
    assert payload["status"] == "completed"


def test_5xx_maps_to_cli_error(monkeypatch, capsys):
    def fake_post(url, **kwargs):
        return FakeResponse(502, {"message": "Reddit Search API request failed"})

    monkeypatch.setattr(cli.requests, "post", fake_post)
    with mock.patch.dict("os.environ", {"AGENT_CONTEXT_API_TOKEN": "tok"}):
        with pytest.raises(cli.RedditSearchCliError, match="502"):
            cli.call_reddit_search(cli.parse_args(["hooks"]))


def test_timeout_maps_to_cli_error(monkeypatch):
    def fake_post(url, **kwargs):
        raise requests.Timeout("too slow")

    monkeypatch.setattr(cli.requests, "post", fake_post)
    with mock.patch.dict("os.environ", {"AGENT_CONTEXT_API_TOKEN": "tok"}):
        with pytest.raises(cli.RedditSearchCliError, match="timed out"):
            cli.call_reddit_search(cli.parse_args(["hooks"]))


def test_unreachable_maps_to_cli_error(monkeypatch):
    def fake_post(url, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(cli.requests, "post", fake_post)
    with mock.patch.dict("os.environ", {"AGENT_CONTEXT_API_TOKEN": "tok"}):
        with pytest.raises(cli.RedditSearchCliError, match="unreachable"):
            cli.call_reddit_search(cli.parse_args(["hooks"]))


# ---------------------------------------------------------------------------
# main() end-to-end with mocked HTTP
# ---------------------------------------------------------------------------


def _run_main(monkeypatch, argv, fake_post):
    monkeypatch.setattr(cli.requests, "post", fake_post)
    with mock.patch.dict("os.environ", {"AGENT_CONTEXT_API_TOKEN": "secret-token"}):
        return cli.main(argv, load_env=False)


def test_main_completed_exit_0(capsys, monkeypatch):
    code = _run_main(monkeypatch, ["hooks query"], lambda url, **kw: FakeResponse(200, _completed_payload()))
    out = capsys.readouterr().out
    assert code == 0
    assert "completed" in out
    assert "secret-token" not in out  # token never printed


def test_main_json_mode(capsys, monkeypatch):
    code = _run_main(monkeypatch, ["hooks query", "--json"], lambda url, **kw: FakeResponse(200, _completed_payload()))
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    assert payload["status"] == "completed"
    assert "secret-token" not in out


def test_main_abstained_exit_0(capsys, monkeypatch):
    code = _run_main(monkeypatch, ["obscure"], lambda url, **kw: FakeResponse(200, {"status": "abstained", "message": "no reliable results"}))
    out = capsys.readouterr().out
    assert code == 0
    assert "abstained" in out


def test_main_technical_error_exit_1(capsys, monkeypatch):
    code = _run_main(monkeypatch, ["hooks"], lambda url, **kw: FakeResponse(502, {"message": "Reddit Search API request failed"}))
    captured = capsys.readouterr()
    assert code == 1
    assert "Error:" in captured.err
    assert "secret-token" not in captured.err + captured.out


def test_main_missing_token_exit_1(capsys, monkeypatch):
    monkeypatch.setattr(cli.requests, "post", lambda url, **kw: FakeResponse(200, {}))
    with mock.patch.dict("os.environ", {}, clear=True):
        code = cli.main(["hooks"], load_env=False)
    captured = capsys.readouterr()
    assert code == 1
    assert "AGENT_CONTEXT_API_TOKEN is required" in captured.err


def test_main_no_query_exit_1(capsys, monkeypatch):
    code = cli.main([], load_env=False)
    captured = capsys.readouterr()
    assert code == 1
    assert "query is required" in captured.err


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor_healthy(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        assert url == "http://localhost:8000/health"
        return FakeResponse(200, {"status": "healthy", "database": "healthy", "diagnostics": {"database": {"status": "healthy"}}})

    monkeypatch.setattr(cli.requests, "get", fake_get)
    with mock.patch.dict("os.environ", {"AGENT_CONTEXT_API_TOKEN": "tok"}):
        code = cli.main(["--doctor"], load_env=False)
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)
    assert report["health_status"] == "healthy"
    assert report["token_configured"] is True


def test_doctor_unreachable_exit_1(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(cli.requests, "get", fake_get)
    code = cli.main(["--doctor"], load_env=False)
    captured = capsys.readouterr()
    assert code == 1
    assert "unreachable" in captured.err


def test_doctor_unhealthy_exit_1(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        return FakeResponse(200, {"status": "degraded", "database": "unhealthy", "diagnostics": {"database": {"status": "unhealthy"}}})

    monkeypatch.setattr(cli.requests, "get", fake_get)
    code = cli.main(["--doctor"], load_env=False)
    assert code == 1


# ---------------------------------------------------------------------------
# config resolution
# ---------------------------------------------------------------------------


def test_api_url_env_override(monkeypatch):
    with mock.patch.dict("os.environ", {"REDDIT_SEARCH_API_URL": "https://panel.example.com/api/v1/agent/reddit-search"}):
        args = cli.parse_args(["q"])
        assert cli.resolve_api_url(args) == "https://panel.example.com/api/v1/agent/reddit-search"


def test_api_url_flag_wins(monkeypatch):
    with mock.patch.dict("os.environ", {"REDDIT_SEARCH_API_URL": "https://env.example.com"}):
        args = cli.parse_args(["q", "--api-url", "https://flag.example.com"])
        assert cli.resolve_api_url(args) == "https://flag.example.com"


def test_invalid_timeout_raises(monkeypatch):
    with mock.patch.dict("os.environ", {"REDDIT_SEARCH_TIMEOUT_SECONDS": "nope"}):
        args = cli.parse_args(["q"])
        with pytest.raises(cli.RedditSearchCliError, match="Invalid timeout"):
            cli.resolve_timeout(args)
