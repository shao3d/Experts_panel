#!/usr/bin/env python3
"""embed_batch save loop: per-post durability.

Regression tests for a silent-loss bug: a mid-batch failure used to roll back
the whole uncommitted batch, dropping the rows that had already saved fine,
while the counter reported them as saved. Also covers the zip() tail-truncation
guard (fewer vectors than posts must fail the batch, not save a prefix).
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
EMBED_PATH = BACKEND_DIR / "scripts" / "embed_posts.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

sqlite_vec = pytest.importorskip("sqlite_vec")

DIM = 8


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def embed_env(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "embed.db"
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.executescript(
        f"""
        CREATE VIRTUAL TABLE vec_posts USING vec0(
            post_id INTEGER PRIMARY KEY,
            embedding float[{DIM}],
            expert_id TEXT PARTITION KEY,
            created_at TEXT
        );
        CREATE TABLE post_embeddings (
            post_id INTEGER PRIMARY KEY,
            embedding_model TEXT,
            dimensions INTEGER,
            embedded_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _load_vec(dbapi_conn, _record):
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
        dbapi_conn.enable_load_extension(False)

    factory = sessionmaker(bind=engine)
    module = _load_module("embed_posts_under_test", EMBED_PATH)
    monkeypatch.setattr(module, "SessionLocal", factory)

    def saved_ids():
        probe = sqlite3.connect(str(db_path))
        probe.enable_load_extension(True)
        sqlite_vec.load(probe)
        probe.enable_load_extension(False)
        rows = sorted(r[0] for r in probe.execute("SELECT post_id FROM vec_posts"))
        probe.close()
        return rows

    return module, saved_ids


class FakeEmbeddingService:
    model = "fake-embed"

    def __init__(self, vectors=None):
        self.vectors = vectors

    async def embed_batch(self, texts, task_type=None):
        if self.vectors is not None:
            return self.vectors
        return [[0.1] * DIM for _ in texts]


def _post(post_id: int, created_at="2026-08-07 00:00:00") -> SimpleNamespace:
    return SimpleNamespace(
        post_id=post_id,
        message_text=f"text of post {post_id} " + "x" * 40,
        created_at=created_at,
        expert_id="video_hub",
    )


def _with_service(module, monkeypatch, service):
    monkeypatch.setattr(module, "get_embedding_service", lambda: service)


async def test_mid_batch_failure_keeps_earlier_and_later_rows(embed_env, monkeypatch):
    module, saved_ids = embed_env
    _with_service(module, monkeypatch, FakeEmbeddingService())
    posts = [
        _post(1),
        _post(2, created_at="не дата"),  # fails the no-guess guard
        _post(3),
    ]

    embedded, errors = await module.embed_batch(posts)

    assert (embedded, errors) == (2, 1)
    assert saved_ids() == [1, 3]  # neighbours survive the failing row


async def test_happy_path_saves_everything(embed_env, monkeypatch):
    module, saved_ids = embed_env
    _with_service(module, monkeypatch, FakeEmbeddingService())

    embedded, errors = await module.embed_batch([_post(1), _post(2)])

    assert (embedded, errors) == (2, 0)
    assert saved_ids() == [1, 2]


async def test_vector_count_mismatch_fails_batch_honestly(embed_env, monkeypatch):
    module, saved_ids = embed_env
    _with_service(module, monkeypatch, FakeEmbeddingService(vectors=[[0.1] * DIM] * 2))

    embedded, errors = await module.embed_batch([_post(1), _post(2), _post(3)])

    assert (embedded, errors) == (0, 3)  # no silent prefix saves, no lying zeros
    assert saved_ids() == []


async def test_embedding_api_failure_reports_all_posts_as_errors(embed_env, monkeypatch):
    module, saved_ids = embed_env

    class BoomService(FakeEmbeddingService):
        async def embed_batch(self, texts, task_type=None):
            raise RuntimeError("api down")

    _with_service(module, monkeypatch, BoomService())

    embedded, errors = await module.embed_batch([_post(1), _post(2)])

    assert (embedded, errors) == (0, 2)
    assert saved_ids() == []


async def test_continuous_stops_after_three_stalled_batches(embed_env, monkeypatch):
    module, _ = embed_env
    calls = []
    async def failed(*args):
        calls.append(1)
        return 0,1
    monkeypatch.setattr(module,'process_batch',failed)
    assert await module.run_continuous(delay=0) == (0,1)
    assert len(calls) == 3


async def test_continuous_can_recover_a_transient_failure(embed_env, monkeypatch):
    module, _ = embed_env
    results = iter([(0,1),(3,0),(0,0)])
    async def process(*args):
        return next(results)
    monkeypatch.setattr(module,'process_batch',process)
    assert await module.run_continuous(delay=0) == (3,0)


@pytest.mark.parametrize('kwargs',[{'dry_run':True},{'force':True}])
async def test_continuous_rejects_modes_that_cannot_advance(embed_env, kwargs):
    module, _ = embed_env
    with pytest.raises(ValueError,match='continuous'):
        await module.run_continuous(**kwargs)


def test_main_propagates_batch_errors(embed_env, monkeypatch):
    module, _ = embed_env
    monkeypatch.setattr(sys,'argv',['embed_posts'])
    monkeypatch.setattr(module,'require_openrouter_runtime',lambda:None)
    async def process(*args):
        return 0,2
    monkeypatch.setattr(module,'process_batch',process)
    assert module.main() == 1


def test_receipt_readiness_requires_each_isolated_source_in_all_indexes(embed_env,tmp_path,monkeypatch):
    import hashlib,json
    from sqlalchemy import text
    module,_=embed_env
    _with_service(module,monkeypatch,FakeEmbeddingService())
    source=tmp_path/'segments.json';source.write_text('{}')
    receipt=tmp_path/'segments.import-receipt.json'
    receipt.write_text(json.dumps({'source_path':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_keys':['video_hub:11','video_hub:22'],'status':'loaded'}))
    with module.SessionLocal() as db:
        db.execute(text('CREATE TABLE posts (post_id INTEGER PRIMARY KEY,expert_id TEXT,telegram_message_id INTEGER)'))
        db.execute(text('CREATE VIRTUAL TABLE posts_fts USING fts5(content)'))
        db.execute(text("INSERT INTO posts VALUES (1,'video_hub',11),(2,'other',22)"))
        db.execute(text("INSERT INTO posts_fts(rowid,content) VALUES (1,'one'),(2,'two')"))
        db.commit()
    awaitable=module.embed_batch([_post(1),_post(2)])
    import asyncio
    assert asyncio.run(awaitable)==(2,0)
    assert not module.verify_receipt_index(receipt)
    with module.SessionLocal() as db:
        db.execute(text("UPDATE posts SET expert_id='video_hub' WHERE post_id=2"));db.commit()
    assert module.verify_receipt_index(receipt)
    with module.SessionLocal() as db:
        db.execute(text('DELETE FROM posts_fts WHERE rowid=2'));db.commit()
    assert not module.verify_receipt_index(receipt)
    assert json.loads(receipt.read_text())['status']=='loaded'
