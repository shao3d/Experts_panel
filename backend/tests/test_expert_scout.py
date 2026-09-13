#!/usr/bin/env python3
"""Unit tests for the read-only Expert Scout helper and output filter."""

from __future__ import annotations

import importlib.util
import io
import sqlite3
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
SCOUT_PATH = BACKEND_DIR / "scripts" / "expert_scout.py"
FILTER_PATH = REPO_ROOT / "scripts" / "expert_scout_filter.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scout():
    return _load_module("expert_scout_under_test", SCOUT_PATH)


def test_parse_source_key_valid_and_invalid(scout):
    assert scout._parse_source_key("refat:238") == ("refat", 238)

    for bad in ["refat", "refat:abc", ":12", "refat:-1"]:
        with pytest.raises(ValueError):
            scout._parse_source_key(bad)


def test_rrf_merge_prefers_ids_found_by_both_retrievers(scout):
    merged = scout._rrf_merge([10, 11], [12, 10], k=60)

    assert merged[0] == 10  # present in both lists wins
    assert set(merged) == {10, 11, 12}


def test_cutoff_iso_format(scout):
    assert scout._cutoff_iso(None) is None
    cutoff = scout._cutoff_iso(7)
    assert cutoff is not None
    assert len(cutoff) == len("2026-01-01 00:00:00")


def test_connect_is_read_only(scout, tmp_path):
    db_path = tmp_path / "sample.db"
    with sqlite3.connect(db_path) as setup:
        setup.execute("CREATE TABLE t (x INTEGER)")
        setup.execute("INSERT INTO t VALUES (1)")
        setup.commit()

    with scout._connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO t VALUES (2)")


def test_resolve_db_path_rejects_outside_backend_data(scout):
    with pytest.raises(SystemExit):
        scout._resolve_db_path(BACKEND_DIR, "/etc/passwd")

    resolved = scout._resolve_db_path(BACKEND_DIR, None)
    assert resolved == (BACKEND_DIR / "data" / "experts.db").resolve()


def test_expert_ids_validates_against_metadata(scout):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")
    conn.executemany(
        "INSERT INTO expert_metadata VALUES (?)", [("refat",), ("akimov",)]
    )

    known, unknown = scout._expert_ids(conn, "refat,bogus")
    assert known == ["refat"]
    assert unknown == ["bogus"]

    all_known, no_unknown = scout._expert_ids(conn, None)
    assert all_known == ["akimov", "refat"]
    assert no_unknown == []


def test_filter_keeps_only_text_after_last_tool(capsys, monkeypatch):
    filter_module = _load_module("expert_scout_filter_under_test", FILTER_PATH)
    events = "\n".join(
        [
            '{"type":"text","part":{"messageID":"m1","text":"narration"}}',
            '{"type":"tool_use","part":{"messageID":"m2","tool":"bash"}}',
            '{"type":"text","part":{"messageID":"m3","text":"FINAL "}}',
            '{"type":"text","part":{"messageID":"m3","text":"ANSWER"}}',
        ]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(events))

    assert filter_module.main() == 0
    assert capsys.readouterr().out.strip() == "FINAL ANSWER"
