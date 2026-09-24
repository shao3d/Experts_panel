#!/usr/bin/env python3
"""Timestamp hygiene for Video Hub: normalization at import, flexible date
parsing in retrieval freshness, and the one-time sweep for legacy rows."""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
IMPORT_PATH = BACKEND_DIR / "scripts" / "import_video_json.py"
SCOUT_PATH = BACKEND_DIR / "scripts" / "expert_scout.py"
SWEEP_PATH = BACKEND_DIR / "scripts" / "maintenance" / "normalize_video_timestamps.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.utils.date_utils import (  # noqa: E402
    format_timestamp,
    parse_timestamp,
    to_canonical_timestamp,
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- date_utils --------------------------------------------------------------


def test_parse_timestamp_accepts_common_shapes():
    assert parse_timestamp("2026-08-07") == datetime(2026, 8, 7, 0, 0, 0)
    assert parse_timestamp("2026-08-21T00:00:00") == datetime(2026, 8, 21, 0, 0, 0)
    assert parse_timestamp("2026-08-21 00:00:00.123456") == datetime(2026, 8, 21, 0, 0, 0, 123456)
    assert parse_timestamp("2026-08-21T12:34:56Z") == datetime(2026, 8, 21, 12, 34, 56)
    assert parse_timestamp("2026-08-21T00:00:00+03:00") == datetime(2026, 8, 20, 21, 0, 0)
    assert parse_timestamp(datetime(2026, 8, 7, 5, 0, 0)) == datetime(2026, 8, 7, 5, 0, 0)


def test_parse_timestamp_rejects_empty_and_garbage():
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None
    assert parse_timestamp("  ") is None
    assert parse_timestamp("вчера") is None
    assert parse_timestamp("07.08.2026") is None


def test_to_canonical_timestamp_normalizes_or_fails_loud():
    assert to_canonical_timestamp("2026-08-07") == "2026-08-07 00:00:00"
    assert to_canonical_timestamp("2026-08-21T00:00:00") == "2026-08-21 00:00:00"
    assert to_canonical_timestamp("2026-08-21T12:34:56.999999") == "2026-08-21 12:34:56"
    assert to_canonical_timestamp(None) is None
    assert to_canonical_timestamp("  ") is None
    with pytest.raises(ValueError):
        to_canonical_timestamp("не дата", field="video_metadata.published_at")


def test_format_timestamp_drops_microseconds():
    assert format_timestamp(datetime(2026, 8, 7, 1, 2, 3, 999999)) == "2026-08-07 01:02:03"


# --- import_video_json: normalization on write -------------------------------


def _make_import_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT, channel_name TEXT, expert_id TEXT,
            message_text TEXT, author_name TEXT, author_id TEXT,
            created_at TEXT, telegram_message_id INTEGER,
            media_metadata TEXT, view_count INTEGER, forward_count INTEGER,
            reply_count INTEGER, is_forwarded INTEGER, channel_username TEXT
        );
        CREATE TABLE expert_metadata (
            expert_id TEXT PRIMARY KEY, display_name TEXT, channel_username TEXT
        );
        CREATE TABLE post_embeddings (post_id INTEGER PRIMARY KEY);
        CREATE TABLE vec_posts (post_id INTEGER PRIMARY KEY, created_at TEXT);
        """
    )
    conn.commit()
    conn.close()


def _vseg(segment_id: int, content: str = "text") -> dict:
    return {
        "segment_id": segment_id,
        "topic_id": "intro",
        "title": f"S{segment_id}",
        "summary": "sum",
        "content": content,
        "timestamp_seconds": 0.0,
    }


def _write_json(path: Path, published_at, segments=None) -> Path:
    meta = {"title": "T", "author": "Author", "url": "https://youtu.be/2b3Z4rW5VJc"}
    if published_at is not None:
        meta["published_at"] = published_at
    payload = {"video_metadata": meta, "segments": segments or [_vseg(1001)]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def import_env(tmp_path, monkeypatch):
    importer = _load_module("import_video_json_dates_test", IMPORT_PATH)
    db_path = tmp_path / "test.db"
    _make_import_db(db_path)
    monkeypatch.setattr(importer, "get_db_path", lambda: db_path)
    return importer, db_path, tmp_path / "segments.json"


def _post_row(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT created_at, json_extract(media_metadata, '$.published_at') FROM posts"
    ).fetchone()
    conn.close()
    return row


def test_import_normalizes_date_only_published_at(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, "2026-08-07"))
    created_at, meta_published = _post_row(db_path)
    assert created_at == "2026-08-07 00:00:00"
    assert meta_published == "2026-08-07 00:00:00"


def test_import_normalizes_iso_t_published_at(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, "2026-08-21T00:00:00"))
    created_at, meta_published = _post_row(db_path)
    assert created_at == "2026-08-21 00:00:00"
    assert meta_published == "2026-08-21 00:00:00"


def test_import_missing_published_at_falls_back_to_canonical_now(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, None))
    created_at, meta_published = _post_row(db_path)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", created_at)
    assert meta_published is None


def test_import_rejects_unparsable_published_at(import_env):
    importer, _db_path, json_path = import_env
    with pytest.raises(SystemExit, match="published_at"):
        importer.import_video_json(_write_json(json_path, "вчера"))


def test_import_update_path_keeps_canonical_created_at(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, "2026-08-07"))
    importer.import_video_json(_write_json(json_path, "2026-08-07", segments=[_vseg(1001, "edited")]))
    created_at, meta_published = _post_row(db_path)
    assert created_at == "2026-08-07 00:00:00"
    assert meta_published == "2026-08-07 00:00:00"


# --- retrieval parsers: date-only is not "ancient" ---------------------------


@pytest.fixture(scope="module")
def scout():
    return _load_module("expert_scout_dates_test", SCOUT_PATH)


def test_scout_parses_date_only_created_at(scout):
    assert scout._parse_created_at("2026-08-07") == datetime(2026, 8, 7)
    assert scout._parse_created_at("2026-08-21T00:00:00") == datetime(2026, 8, 21)
    assert scout._parse_created_at("garbage") is None


def test_scout_freshness_does_not_floor_date_only_rows(scout):
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    fresh = scout._soft_freshness("2026-08-07", now)
    assert fresh > 0.7  # not bucketed as maximally old
    assert scout._soft_freshness("2020-01-01", now) == 0.7  # genuinely old floored
    assert scout._soft_freshness(None, now) == 0.7


def test_hybrid_age_days_accepts_date_only():
    from src.services.hybrid_retrieval_service import HybridRetrievalService

    svc = HybridRetrievalService.__new__(HybridRetrievalService)
    today = datetime.utcnow().date().isoformat()
    assert svc._calculate_age_days(today) == 0
    assert svc._calculate_age_days("garbage") == 365
    assert svc._calculate_age_days(None) == 365


# --- sweep: heal legacy rows in posts / posts_fts / vec_posts ----------------


@pytest.fixture()
def sweep():
    return _load_module("normalize_video_timestamps_test", SWEEP_PATH)


def _make_sweep_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE posts (
            post_id INTEGER PRIMARY KEY,
            expert_id TEXT, created_at TEXT, media_metadata TEXT
        );
        CREATE VIRTUAL TABLE posts_fts USING fts5(
            content, expert_id UNINDEXED, created_at UNINDEXED
        );
        CREATE TABLE vec_posts (post_id INTEGER PRIMARY KEY, created_at TEXT);
        """
    )
    rows = [
        (1, "video_hub", "2026-08-07",
         json.dumps({"type": "video_segment", "published_at": "2026-08-07"})),
        (2, "video_hub", "2026-08-21 00:00:00",
         json.dumps({"type": "video_segment", "published_at": "2026-08-21 00:00:00"})),
        (3, "video_hub", "не дата",
         json.dumps({"type": "video_segment"})),
        (4, "refat", "2026-08-07", None),
    ]
    conn.executemany(
        "INSERT INTO posts (post_id, expert_id, created_at, media_metadata) VALUES (?,?,?,?)",
        rows,
    )
    conn.execute(
        "INSERT INTO posts_fts(rowid, content, expert_id, created_at) VALUES (1, 'segment text here', 'video_hub', '2026-08-07')"
    )
    conn.execute(
        "INSERT INTO posts_fts(rowid, content, expert_id, created_at) VALUES (4, 'telegram post text', 'refat', '2026-08-07')"
    )
    conn.execute("INSERT INTO vec_posts (post_id, created_at) VALUES (1, '2026-08-07')")
    conn.execute("INSERT INTO vec_posts (post_id, created_at) VALUES (4, '2026-08-07')")
    conn.commit()
    conn.close()


def test_sweep_heals_legacy_video_rows_only(sweep, tmp_path):
    db_path = tmp_path / "sweep.db"
    _make_sweep_db(db_path)

    counts = sweep.normalize_video_timestamps(db_path)
    assert counts["scanned"] == 3
    assert counts["updated_posts"] == 1
    assert counts["updated_meta_published"] == 1
    assert counts["updated_fts"] == 1
    assert counts["updated_vec"] == 1
    assert counts["already_canonical"] == 1
    assert counts["unparsable"] == 1
    assert counts["vec_verify_failed"] == 0

    conn = sqlite3.connect(str(db_path))
    posts = dict(conn.execute("SELECT post_id, created_at FROM posts").fetchall())
    fts = dict(conn.execute("SELECT rowid, created_at FROM posts_fts").fetchall())
    vec = dict(conn.execute("SELECT post_id, created_at FROM vec_posts").fetchall())
    meta_published = conn.execute(
        "SELECT json_extract(media_metadata, '$.published_at') FROM posts WHERE post_id = 1"
    ).fetchone()[0]
    conn.close()

    assert posts[1] == "2026-08-07 00:00:00"
    assert meta_published == "2026-08-07 00:00:00"
    assert posts[2] == "2026-08-21 00:00:00"
    assert posts[3] == "не дата"  # unparsable left untouched
    assert posts[4] == "2026-08-07"  # non-video row untouched
    assert fts[1] == "2026-08-07 00:00:00"
    assert fts[4] == "2026-08-07"
    assert vec[1] == "2026-08-07 00:00:00"
    assert vec[4] == "2026-08-07"


def test_sweep_dry_run_changes_nothing(sweep, tmp_path):
    db_path = tmp_path / "sweep.db"
    _make_sweep_db(db_path)

    counts = sweep.normalize_video_timestamps(db_path, dry_run=True)
    assert counts["updated_posts"] == 1

    conn = sqlite3.connect(str(db_path))
    created = conn.execute("SELECT created_at FROM posts WHERE post_id = 1").fetchone()[0]
    conn.close()
    assert created == "2026-08-07"  # untouched in dry-run
