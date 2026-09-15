#!/usr/bin/env python3
"""Unit tests for the read-only Expert Scout helper and output filter."""

from __future__ import annotations

import importlib.util
import io
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
SCOUT_PATH = BACKEND_DIR / "scripts" / "expert_scout.py"
FILTER_PATH = REPO_ROOT / "scripts" / "expert_scout_filter.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


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


def test_expert_ids_resolves_canonical_group(scout):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")
    conn.executemany(
        "INSERT INTO expert_metadata VALUES (?)",
        [("acidcrunch",), ("strangedalle",), ("cgevent",), ("neyrograph",), ("refat",)],
    )

    known, unknown = scout._expert_ids(conn, None, "visual")
    assert known == ["strangedalle", "acidcrunch", "cgevent", "neyrograph"]
    assert unknown == []

    known_tb, _ = scout._expert_ids(conn, None, "tech_business")
    assert known_tb == ["refat"]


def test_expert_ids_rejects_unknown_group(scout):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE expert_metadata (expert_id TEXT)")

    with pytest.raises(ValueError, match="unknown expert group"):
        scout._expert_ids(conn, None, "bogus")


def test_expert_groups_shared_module_is_canonical():
    from src.expert_groups import AGENT_CONTEXT_EXPERT_GROUPS, groups_for_expert

    assert "visual" in AGENT_CONTEXT_EXPERT_GROUPS
    assert "strangedalle" in AGENT_CONTEXT_EXPERT_GROUPS["visual"]
    assert groups_for_expert("acidcrunch") == ["visual"]
    assert groups_for_expert("cgevent") == ["visual"]
    assert groups_for_expert("neyrograph") == ["visual"]
    assert groups_for_expert("refat") == ["tech_business"]
    assert groups_for_expert("mkarpov") == []


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


def test_filter_marks_fallback_narration(capsys, monkeypatch):
    filter_module = _load_module("expert_scout_filter_fallback", FILTER_PATH)
    events = "\n".join(
        [
            '{"type":"text","part":{"messageID":"m1","text":"thinking out loud"}}',
            '{"type":"tool_use","part":{"messageID":"m2","tool":"scout"}}',
        ]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(events))

    assert filter_module.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("# WARNING")
    assert "thinking out loud" in out


def test_soft_freshness_parses_both_formats_and_floors(scout):
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    one_day_space = scout._soft_freshness("2026-09-12 12:00:00.000000", now)
    one_day_iso = scout._soft_freshness("2026-09-12T12:00:00", now)

    assert one_day_space == pytest.approx(one_day_iso)
    assert one_day_space == pytest.approx(1 - 1 / 365, abs=1e-6)
    assert scout._soft_freshness("2020-01-01 00:00:00", now) == 0.7
    assert scout._soft_freshness(None, now) == 0.7
    assert scout._soft_freshness("garbage", now) == 0.7


def test_rank_fts_demotes_stale_strong_match(scout):
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    rows = [
        (1, "s1", -6.0, "2023-01-01 00:00:00.000000"),  # better BM25, stale
        (2, "s2", -5.0, "2026-09-12 00:00:00"),  # slightly weaker, fresh
    ]

    assert scout._rank_fts(rows, now) == [2, 1]


def test_rank_vector_prefers_fresh_relevant(scout):
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    rows = [
        (1, 0.10, "2023-01-01 00:00:00.000000"),  # closest, stale
        (2, 0.30, "2026-09-12 00:00:00"),  # farther, fresh
    ]

    assert scout._rank_vector(rows, now)[:1] == [2]


@pytest.fixture()
def show_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE posts (
            post_id INTEGER PRIMARY KEY, expert_id TEXT, telegram_message_id INTEGER,
            channel_username TEXT, created_at TEXT, author_name TEXT, author_id TEXT,
            message_text TEXT, reply_count INTEGER, view_count INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE comments (
            comment_id INTEGER PRIMARY KEY, post_id INTEGER, comment_text TEXT,
            author_id TEXT, author_name TEXT, created_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE TABLE links (source_post_id INTEGER, target_post_id INTEGER, link_type TEXT)"
    )
    conn.execute(
        "INSERT INTO posts VALUES (1, 'acidcrunch', 2062, 'AcidCrunch',"
        " '2025-06-05 10:00:00.000000', 'Acid', 'channel55', 'post text', 3, 100)"
    )
    for i in range(6):
        conn.execute(
            "INSERT INTO comments VALUES (?, 1, ?, '999', ?, ?)",
            (i + 1, f"community {i}", f"user{i}", f"2025-06-05 11:{i:02d}:00.000000"),
        )
    # Late author replies would fall outside the chronological comment window.
    conn.execute(
        "INSERT INTO comments VALUES (20, 1, 'author answer', '55', 'Acid',"
        " '2025-06-06 10:00:00.000000')"
    )
    conn.execute(
        "INSERT INTO comments VALUES (21, 1, 'author answer 2', '55', 'Acid',"
        " '2025-06-06 11:00:00.000000')"
    )
    conn.execute(
        "INSERT INTO posts VALUES (2, 'acidcrunch', 2070, 'AcidCrunch',"
        " '2025-06-07 10:00:00.000000', 'Acid', 'channel55', 'linked post text', 0, 5)"
    )
    conn.execute("INSERT INTO links VALUES (1, 2, 'reply')")
    conn.commit()
    return conn


def test_collect_show_payload_keeps_late_author_comments(scout, show_conn):
    payload = scout._collect_show_payload(show_conn, ["acidcrunch:2062"], 5)
    item = payload[0]

    author = [c for c in item["comments"] if c["is_author"]]
    community = [c for c in item["comments"] if not c["is_author"]]
    assert len(author) == 2  # both late author replies are kept
    assert len(community) == 5  # community window stays capped
    assert item["linked_context"][0]["source_key"] == "acidcrunch:2070"


def test_collect_show_payload_reports_bad_keys(scout, show_conn):
    payload = scout._collect_show_payload(
        show_conn, ["acidcrunch:abc", "acidcrunch:999999"], 5
    )

    assert payload[0]["error"].startswith("invalid source_key")
    assert payload[1]["error"] == "not_found"
