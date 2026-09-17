#!/usr/bin/env python3
"""Guards for the VideoHub ingest/import path (fail-loud validation).

Covers the review follow-ups:
- `combine_chunks` rejects duplicate segment_id and strips chunk-local metadata
- `canonical_video_url` maps every YouTube URL form to one identity
- `render_visual_block` keeps unknown scalar visual keys searchable
- `validate_transcript_schema` rejects foreign-format transcripts
- import: duplicate virtual IDs abort, text changes invalidate embeddings,
  `--replace-video` consolidates re-segmented videos
- `VideoHubService._normalize_scores` drops phantom Map scores and dedups
  duplicates to the strongest relevance per segment
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
INGEST_PATH = BACKEND_DIR / "scripts" / "ingest_video.py"
IMPORT_PATH = BACKEND_DIR / "scripts" / "import_video_json.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ingest():
    return _load_module("ingest_video_under_test", INGEST_PATH)


@pytest.fixture(scope="module")
def importer():
    return _load_module("import_video_json_under_test", IMPORT_PATH)


# --- canonical_video_url ----------------------------------------------------

CANONICAL = "https://www.youtube.com/watch?v=2b3Z4rW5VJc"


@pytest.mark.parametrize(
    "raw",
    [
        "2b3Z4rW5VJc",
        "https://youtu.be/2b3Z4rW5VJc",
        "https://youtu.be/2b3Z4rW5VJc?si=abc123",
        "https://www.youtube.com/watch?v=2b3Z4rW5VJc",
        "https://www.youtube.com/watch?v=2b3Z4rW5VJc&list=xyz&t=10s",
        "https://m.youtube.com/watch?v=2b3Z4rW5VJc",
        "https://www.youtube.com/shorts/2b3Z4rW5VJc",
        "https://www.youtube.com/embed/2b3Z4rW5VJc",
        "https://www.youtube.com/live/2b3Z4rW5VJc",
    ],
)
def test_canonical_video_url_unifies_forms(importer, raw):
    assert importer.canonical_video_url(raw) == CANONICAL


def test_canonical_video_url_passthrough_non_youtube(importer):
    url = "https://example.com/videos/lecture.mp4"
    assert importer.canonical_video_url(url) == url


def test_virtual_id_stable_across_url_forms(importer):
    ids = {
        importer.generate_virtual_id(importer.canonical_video_url(raw), 1001)
        for raw in ("2b3Z4rW5VJc", "https://youtu.be/2b3Z4rW5VJc")
    }
    assert len(ids) == 1


# --- combine_chunks ----------------------------------------------------------


def _write_chunk(out_dir: Path, name: str, segments: list, meta_extra: dict | None = None):
    chunk_dir = out_dir / "chunks" / name
    chunk_dir.mkdir(parents=True, exist_ok=True)
    meta = {"title": "T", "url": "https://youtu.be/2b3Z4rW5VJc"}
    if meta_extra:
        meta.update(meta_extra)
    (chunk_dir / "segments.json").write_text(
        json.dumps({"video_metadata": meta, "segments": segments}), encoding="utf-8"
    )


def _seg(segment_id: int, ts: float):
    return {
        "segment_id": segment_id,
        "topic_id": "intro",
        "title": f"S{segment_id}",
        "summary": "sum",
        "content": "text",
        "timestamp_seconds": ts,
    }


def test_combine_merges_and_strips_chunk_metadata(ingest, tmp_path):
    _write_chunk(
        tmp_path, "chunk_01", [_seg(1001, 10.0)],
        {"chunk": 1, "chunk_range_s": [0.0, 300.0]},
    )
    _write_chunk(tmp_path, "chunk_02", [_seg(1002, 310.0)], {"chunk": 2})
    payload = ingest.combine_chunks(tmp_path, 25.0)
    assert [s["segment_id"] for s in payload["segments"]] == [1001, 1002]
    assert payload["video_metadata"]["chunks_combined"] == 2
    assert "chunk" not in payload["video_metadata"]
    assert "chunk_range_s" not in payload["video_metadata"]


def test_combine_rejects_duplicate_segment_id(ingest, tmp_path):
    _write_chunk(tmp_path, "chunk_01", [_seg(1001, 10.0)])
    _write_chunk(tmp_path, "chunk_02", [_seg(1001, 290.0)])
    with pytest.raises(SystemExit, match="duplicate segment_id"):
        ingest.combine_chunks(tmp_path, 25.0)


def test_combine_rejects_non_object_segment(ingest, tmp_path):
    _write_chunk(tmp_path, "chunk_01", [_seg(1001, 10.0)])
    _write_chunk(tmp_path, "chunk_02", ["junk"])
    with pytest.raises(SystemExit, match="non-object segment"):
        ingest.combine_chunks(tmp_path, 25.0)


# --- render_visual_block -----------------------------------------------------


def test_render_visual_block_keeps_unknown_scalars(importer):
    block = importer.render_visual_block(
        {
            "kind": "prompt_panel",
            "model": "Seedance 2.5",
            "seed": 12345,
            "negative_prompt": "blurry, watermark",
            "nested": {"a": 1},
            "items": ["x", "y"],
        }
    )
    assert "model: Seedance 2.5" in block
    assert "seed: 12345" in block
    assert "negative_prompt: blurry, watermark" in block
    assert "nested" not in block
    assert "items" not in block


# --- validate_transcript_schema ----------------------------------------------


def _transcript(items: list) -> dict:
    return {"segments": items}


def test_validate_transcript_schema_ok(ingest):
    ingest.validate_transcript_schema(
        _transcript([{"start": 0.0, "end": 1.5, "text": "hi"}]), "test"
    )


def test_validate_transcript_schema_rejects(ingest):
    with pytest.raises(SystemExit, match="no non-empty 'segments'"):
        ingest.validate_transcript_schema({}, "test")
    with pytest.raises(SystemExit, match="lack numeric start/end"):
        ingest.validate_transcript_schema(
            _transcript([{"start": "zero", "end": 1.0, "text": "hi"}]), "test"
        )
    with pytest.raises(SystemExit, match="lack numeric start/end"):
        ingest.validate_transcript_schema(
            _transcript([{"begin": 0.0, "finish": 1.0, "text": "hi"}]), "test"
        )
    with pytest.raises(SystemExit, match="lack numeric start/end"):
        ingest.validate_transcript_schema(
            _transcript([{"start": True, "end": 1.0, "text": "hi"}]), "test"
        )


# --- VideoHubService._normalize_scores ----------------------------------------


def _post(telegram_message_id: int):
    return SimpleNamespace(telegram_message_id=telegram_message_id)


def test_normalize_scores_drops_phantoms():
    from src.services.video_hub_service import VideoHubService

    segments = [_post(111), _post(222)]
    raw = [
        {"id": 111, "relevance": "HIGH", "reason": "dropped anyway"},
        {"id": 999, "relevance": "HIGH"},
        {"id": 222, "relevance": "MAYBE"},
        {"id": "222", "relevance": "MEDIUM"},
        {"id": 111.0, "relevance": "HIGH"},
        {"id": True, "relevance": "HIGH"},
        {"noid": True},
        "junk",
    ]
    cleaned = VideoHubService._normalize_scores(raw, segments)
    assert cleaned == [
        {"id": 111, "relevance": "HIGH"},
        {"id": "222", "relevance": "MEDIUM"},
    ]


def test_normalize_scores_dedups_to_strongest():
    from src.services.video_hub_service import VideoHubService

    segments = [_post(111), _post(222)]
    raw = [
        {"id": 111, "relevance": "LOW"},
        {"id": 111, "relevance": "HIGH"},
        {"id": 222, "relevance": "MEDIUM"},
        {"id": 222, "relevance": "LOW"},
    ]
    cleaned = VideoHubService._normalize_scores(raw, segments)
    assert cleaned == [
        {"id": 111, "relevance": "HIGH"},
        {"id": 222, "relevance": "MEDIUM"},
    ]


def test_normalize_scores_non_list():
    from src.services.video_hub_service import VideoHubService

    assert VideoHubService._normalize_scores({"scores": []}, [_post(1)]) == []


# --- import_video_json integration (isolated tmp DB) --------------------------


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
        CREATE TABLE vec_posts (post_id INTEGER PRIMARY KEY);
        """
    )
    conn.commit()
    conn.close()


def _write_json(path: Path, segments: list, url: str = "https://youtu.be/2b3Z4rW5VJc") -> Path:
    payload = {
        "video_metadata": {
            "title": "T",
            "author": "Author",
            "url": url,
            "published_at": "2026-08-21T00:00:00",
        },
        "segments": segments,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _vseg(segment_id: int, ts: float, content: str = "text") -> dict:
    return {
        "segment_id": segment_id,
        "topic_id": "intro",
        "title": f"S{segment_id}",
        "summary": "sum",
        "content": content,
        "timestamp_seconds": ts,
    }


@pytest.fixture()
def import_env(importer, tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    _make_import_db(db_path)
    monkeypatch.setattr(importer, "get_db_path", lambda: db_path)
    json_path = tmp_path / "segments.json"
    return importer, db_path, json_path


def _rows(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT telegram_message_id, message_text, channel_username,"
        " json_extract(media_metadata, '$.video_url') FROM posts"
    ).fetchall()
    conn.close()
    return rows


def test_import_stores_canonical_url_and_handle(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, [_vseg(1001, 0.0), _vseg(1002, 60.0)]))
    rows = _rows(db_path)
    assert len(rows) == 2
    assert {r[2] for r in rows} == {"video_hub_internal"}
    assert {r[3] for r in rows} == {"https://www.youtube.com/watch?v=2b3Z4rW5VJc"}


def test_import_rejects_duplicate_virtual_id(import_env):
    importer, _db_path, json_path = import_env
    dup = [_vseg(1001, 0.0), dict(_vseg(1001, 30.0))]
    with pytest.raises(SystemExit, match="duplicate segment identity"):
        importer.import_video_json(_write_json(json_path, dup))


def test_import_text_change_invalidates_embeddings(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, [_vseg(1001, 0.0)]))
    conn = sqlite3.connect(str(db_path))
    post_id = conn.execute("SELECT post_id FROM posts").fetchone()[0]
    conn.execute("INSERT INTO post_embeddings (post_id) VALUES (?)", (post_id,))
    conn.execute("INSERT INTO vec_posts (post_id) VALUES (?)", (post_id,))
    conn.commit()
    conn.close()

    importer.import_video_json(_write_json(json_path, [_vseg(1001, 0.0, content="edited")]))
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM post_embeddings").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM vec_posts").fetchone()[0] == 0
        text = conn.execute("SELECT message_text FROM posts").fetchone()[0]
        assert "edited" in text
    finally:
        conn.close()


def test_import_replace_video_consolidates_resegmentation(import_env):
    importer, db_path, json_path = import_env
    importer.import_video_json(_write_json(json_path, [_vseg(1001, 0.0), _vseg(1002, 60.0)]))
    conn = sqlite3.connect(str(db_path))
    before = {r[0] for r in conn.execute("SELECT telegram_message_id FROM posts").fetchall()}
    conn.close()
    assert len(before) == 2

    counts = importer.import_video_json(
        _write_json(json_path, [_vseg(1001, 0.0), _vseg(1003, 120.0)]),
        replace_video=True,
    )
    assert counts["replaced"] == 2
    rows = _rows(db_path)
    assert len(rows) == 2
    texts = " ".join(r[1] for r in rows)
    assert "S1003" in texts and "S1002" not in texts
