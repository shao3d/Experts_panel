#!/usr/bin/env python3
"""Unit tests for standalone CLI bootstrap helpers."""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (
    get_sqlite_db_path,
    get_postgres_database_url,
    resolve_backend_dir,
    set_default_sqlite_database_url,
)


def test_resolve_backend_dir_finds_backend_root():
    target = BACKEND_DIR / "scripts" / "embed_posts.py"
    assert resolve_backend_dir(target) == BACKEND_DIR.resolve()


def test_set_default_sqlite_database_url_normalizes_relative_sqlite_path(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/experts.db")

    resolved = set_default_sqlite_database_url(BACKEND_DIR)

    assert resolved == (BACKEND_DIR / "data" / "experts.db").resolve()
    assert os.environ["DATABASE_URL"] == f"sqlite:///{resolved}"


def test_get_postgres_database_url_rejects_sqlite(monkeypatch):
    monkeypatch.delenv("POSTGRES_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/experts.db")

    try:
        get_postgres_database_url()
    except RuntimeError as exc:
        assert "must point to PostgreSQL" in str(exc)
    else:
        raise AssertionError("Expected get_postgres_database_url() to reject sqlite URLs")


def test_get_postgres_database_url_prefers_explicit_postgres_env(monkeypatch):
    postgres_url = "postgresql://user:pass@localhost:5432/experts"
    monkeypatch.setenv("POSTGRES_DATABASE_URL", postgres_url)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/experts.db")

    assert get_postgres_database_url() == postgres_url


def test_get_sqlite_db_path_normalizes_relative_env_path_to_backend_dir(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/experts.db")

    resolved = get_sqlite_db_path(BACKEND_DIR)

    assert resolved == (BACKEND_DIR / "data" / "experts.db").resolve()
    assert os.environ["DATABASE_URL"] == f"sqlite:///{resolved}"
