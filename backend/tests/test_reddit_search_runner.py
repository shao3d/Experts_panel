#!/usr/bin/env python3
"""Contract tests for scripts/reddit_search_runner.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[2]
RUNNER = ROOT / "scripts" / "reddit_search_runner.py"


def run_runner(*args: str, env: dict[str, str] | None = None):
    merged = os.environ.copy()
    if env is not None:
        merged.clear()
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=Path("/tmp"),
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def test_requires_query():
    result = run_runner(env={"PATH": os.environ.get("PATH", "")})
    assert result.returncode == 1
    assert "query is required" in result.stderr


def test_requires_token_for_search():
    result = run_runner("hooks", env={"PATH": os.environ.get("PATH", "")})
    assert result.returncode == 1
    assert "AGENT_CONTEXT_API_TOKEN" in result.stderr


def test_doctor_uses_health_endpoint():
    import importlib.util

    spec = importlib.util.spec_from_file_location("reddit_search_runner", RUNNER)
    runner = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(runner)

    class Response:
        status = 200

        def read(self):
            return b'{"status":"healthy","database":"healthy"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    args = runner.parse_args(["--doctor", "--api-url", "https://panel.example/api/v1/agent/reddit-search"])
    with patch.object(runner.urllib.request, "urlopen", return_value=Response()) as urlopen:
        report = runner.doctor(args)
    assert report["health_status"] == "healthy"
    assert report["database"] == "healthy"
    assert urlopen.call_args.args[0].full_url == "https://panel.example/health"


def test_print_human_completed(capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("reddit_search_runner", RUNNER)
    runner = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(runner)

    code = runner.print_human(
        {
            "status": "completed",
            "answer": "Useful answer",
            "found_count": 2,
            "sources": [{"title": "Thread", "url": "https://reddit.com/r/test/comments/a", "subreddit": "test"}],
        }
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Useful answer" in out
    assert "https://reddit.com/r/test" in out


def test_print_human_abstained_is_success(capsys):
    import importlib.util

    spec = importlib.util.spec_from_file_location("reddit_search_runner", RUNNER)
    runner = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(runner)

    code = runner.print_human({"status": "abstained", "message": "No reliable results"})
    assert code == 0
    assert "abstained" in capsys.readouterr().out
