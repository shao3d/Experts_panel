#!/usr/bin/env python3
"""Tests for backend durable result artifact retention cleanup."""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.services.artifact_retention_service import (  # noqa: E402
    cleanup_json_artifacts,
    cleanup_result_artifacts,
)


def test_cleanup_json_artifacts_removes_only_expired_top_level_json(tmp_path):
    now = 1_800_000_000.0
    directory = tmp_path / "query_results"
    nested = directory / "nested"
    nested.mkdir(parents=True)

    old_json = directory / "old.json"
    fresh_json = directory / "fresh.json"
    old_tmp = directory / "old.json.tmp"
    nested_old_json = nested / "nested-old.json"
    for path in [old_json, fresh_json, old_tmp, nested_old_json]:
        path.write_text("{}", encoding="utf-8")

    old_time = now - (8 * 86400)
    fresh_time = now - (1 * 86400)
    os.utime(old_json, (old_time, old_time))
    os.utime(old_tmp, (old_time, old_time))
    os.utime(nested_old_json, (old_time, old_time))
    os.utime(fresh_json, (fresh_time, fresh_time))

    result = cleanup_json_artifacts(
        name="query_results",
        directory=directory,
        ttl_days=7,
        now=now,
    )

    assert result["deleted_count"] == 1
    assert result["deleted_bytes"] == 2
    assert not old_json.exists()
    assert fresh_json.exists()
    assert old_tmp.exists()
    assert nested_old_json.exists()


def test_cleanup_result_artifacts_uses_configured_dirs_and_ttls(monkeypatch, tmp_path):
    now = 1_800_000_000.0
    query_dir = tmp_path / "query_results"
    agent_dir = tmp_path / "agent_context_results"
    query_dir.mkdir()
    agent_dir.mkdir()
    old_time = now - (8 * 86400)

    query_old = query_dir / "query-old.json"
    agent_old = agent_dir / "agent-old.json"
    query_old.write_text("{}", encoding="utf-8")
    agent_old.write_text("{}", encoding="utf-8")
    os.utime(query_old, (old_time, old_time))
    os.utime(agent_old, (old_time, old_time))

    monkeypatch.setattr(config, "QUERY_RESULTS_DIR", str(query_dir))
    monkeypatch.setattr(config, "AGENT_CONTEXT_RESULTS_DIR", str(agent_dir))
    monkeypatch.setattr(config, "QUERY_RESULTS_TTL_DAYS", 7)
    monkeypatch.setattr(config, "AGENT_CONTEXT_RESULTS_TTL_DAYS", 7)

    result = cleanup_result_artifacts(now=now)

    assert result["deleted_count"] == 2
    assert result["deleted_bytes"] == 4
    assert not query_old.exists()
    assert not agent_old.exists()


def test_cleanup_json_artifacts_skips_non_positive_ttl(tmp_path):
    directory = tmp_path / "query_results"
    directory.mkdir()
    old_json = directory / "old.json"
    old_json.write_text("{}", encoding="utf-8")

    result = cleanup_json_artifacts(
        name="query_results",
        directory=directory,
        ttl_days=0,
    )

    assert result["skipped"] is True
    assert result["deleted_count"] == 0
    assert old_json.exists()
