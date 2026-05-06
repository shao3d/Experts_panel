#!/usr/bin/env python3
"""Regression tests for FTS5 query sanitization used by hybrid retrieval."""

import os
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src.services.ai_scout_service import AIScoutService
from src.services.fts5_retrieval_service import sanitize_fts5_query


def _assert_fts5_accepts(match_query: str) -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE posts_fts USING fts5(content)")
        conn.execute(
            "INSERT INTO posts_fts(content) VALUES (?)",
            (
                "file fist file first метод embeddings эмбеддинги vector "
                "не всегда хорошо",
            ),
        )
        conn.execute(
            "SELECT rowid FROM posts_fts WHERE posts_fts MATCH ?",
            (match_query,),
        ).fetchall()
    finally:
        conn.close()


def test_sanitize_fts5_query_splits_hyphenated_and_punctuated_terms():
    dirty_query = (
        "такое* OR file-fist* OR метод?* OR прочему* OR эмбеддинги* "
        "OR embedding OR vector OR это* OR не* OR container OR всегда* OR хорошо?*"
    )

    clean_query = sanitize_fts5_query(dirty_query)

    assert "file-fist" not in clean_query
    assert "метод?*" not in clean_query
    assert "хорошо?*" not in clean_query
    assert "file*" in clean_query
    assert "fist*" in clean_query
    assert "метод*" in clean_query
    assert "хорошо*" in clean_query
    _assert_fts5_accepts(clean_query)


def test_sanitize_fts5_query_recovers_from_unbalanced_scout_quote():
    dirty_query = (
        'file-fist OR "file fist" OR rag OR embedding* '
        'OR vector* OR "не всегда хорошо'
    )

    clean_query = sanitize_fts5_query(dirty_query)

    assert clean_query.count('"') % 2 == 0
    assert "file-fist" not in clean_query
    _assert_fts5_accepts(clean_query)


def test_ai_scout_fallback_generates_fts5_safe_terms_for_user_punctuation():
    scout = AIScoutService.__new__(AIScoutService)

    fallback_query = scout._generate_fallback(
        "Что такое file-fist метод? Прочему эмбеддинги - это не всегда хорошо?"
    )

    assert "file-fist" not in fallback_query
    assert "метод?*" not in fallback_query
    assert "хорошо?*" not in fallback_query
    assert "file*" in fallback_query
    assert "fist*" in fallback_query
    assert "эмбеддинги*" in fallback_query
    _assert_fts5_accepts(fallback_query)
