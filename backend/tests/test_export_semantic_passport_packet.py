from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "export_semantic_passport_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("export_semantic_passport_packet", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE expert_metadata (
            expert_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            channel_username TEXT NOT NULL
        );
        CREATE TABLE posts (
            post_id INTEGER PRIMARY KEY,
            expert_id TEXT,
            telegram_message_id INTEGER,
            message_text TEXT,
            created_at TEXT,
            view_count INTEGER,
            forward_count INTEGER,
            reply_count INTEGER
        );
        CREATE TABLE comments (
            comment_id INTEGER PRIMARY KEY,
            post_id INTEGER NOT NULL,
            comment_text TEXT NOT NULL,
            author_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            telegram_comment_id INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO expert_metadata VALUES (?, ?, ?)",
        ("refat", "Refat (Tech & AI)", "nobilix"),
    )
    conn.executemany(
        """
        INSERT INTO posts
        (post_id, expert_id, telegram_message_id, message_text, created_at, view_count, forward_count, reply_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "refat",
                101,
                "A practical post about AI agents, product workflow, and eval discipline.",
                "2026-05-01 10:00:00",
                100,
                2,
                1,
            ),
            (
                2,
                "refat",
                102,
                "A second post about RAG, retrieval quality, and implementation pitfalls.",
                "2026-05-02 10:00:00",
                200,
                3,
                2,
            ),
        ],
    )
    conn.executemany(
        """
        INSERT INTO comments
        (comment_id, post_id, comment_text, author_name, created_at, telegram_comment_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (10, 1, "This matched our team experience.", "Alice", "2026-05-01 11:00:00", 1001),
            (11, 1, "Can you show a checklist?", "Bob", "2026-05-01 12:00:00", 1002),
            (12, 2, "Retrieval failures are common.", "Carol", "2026-05-02 11:00:00", 1003),
        ],
    )
    return conn


def test_write_packet_nests_comments_under_posts(tmp_path):
    module = load_module()
    conn = make_db()
    expert = module.fetch_expert(conn, "refat")
    posts = module.fetch_posts(conn, "refat", max_posts=None)
    comments = module.fetch_comments(
        conn,
        "refat",
        {post.post_id: post.source_ref for post in posts},
        max_comments_per_post=None,
    )

    manifest = module.write_packet(
        expert=expert,
        posts=posts,
        comments_by_post_id=comments,
        output_dir=tmp_path,
        model="gemini-3.1-pro-preview",
        max_comments_per_post=None,
    )

    corpus = (tmp_path / "refat_corpus.md").read_text(encoding="utf-8")
    prompt = (tmp_path / "semantic_passport_prompt.md").read_text(encoding="utf-8")
    schema = json.loads((tmp_path / "expert_value_passport_schema_v1_1.json").read_text(encoding="utf-8"))
    source_ref_index = json.loads((tmp_path / "refat_source_ref_index.json").read_text(encoding="utf-8"))
    combined = (tmp_path / "refat_vertex_prompt.md").read_text(encoding="utf-8")

    assert manifest["corpus_stats"]["post_count"] == 2
    assert manifest["corpus_stats"]["comment_count"] == 3
    assert "## SOURCE P0001" in corpus
    assert "#### COMMENT P0001.C0001" in corpus
    assert "#### COMMENT P0001.C0002" in corpus
    assert "#### COMMENT P0002.C0001" in corpus
    assert "Comments are community signal" in corpus
    assert "Return strict JSON only" in prompt
    assert "matrix_export" in prompt
    assert "not_scored_without_matrix" in prompt
    assert schema["schema_version"] == "expert_value_passport.v1.1"
    assert "source_ref_index_used" in schema["required"]
    assert "query_intent_fit" in schema["required"]
    assert "content_quality_distribution" in schema["required"]
    assert "matrix_export" in schema["required"]
    assert manifest["files"]["source_ref_index"] == "refat_source_ref_index.json"
    assert manifest["artifact_stats"]["source_ref_count"] == 5
    assert source_ref_index[0]["source_ref"] == "P0001"
    assert source_ref_index[0]["telegram_message_id"] == 101
    assert source_ref_index[1]["source_ref"] == "P0001.C0001"
    assert source_ref_index[1]["source_kind"] == "community_comment"
    assert "Return the strict JSON passport now." in combined


def test_comment_cap_is_per_post():
    module = load_module()
    conn = make_db()
    expert = module.fetch_expert(conn, "refat")
    posts = module.fetch_posts(conn, "refat", max_posts=None)
    comments = module.fetch_comments(
        conn,
        expert.expert_id,
        {post.post_id: post.source_ref for post in posts},
        max_comments_per_post=1,
    )

    assert [comment.source_ref for comment in comments[1]] == ["P0001.C0001"]
    assert [comment.source_ref for comment in comments[2]] == ["P0002.C0001"]
