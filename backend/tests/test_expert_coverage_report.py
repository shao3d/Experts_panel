from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "expert_coverage_report.py"


def load_module():
    spec = importlib.util.spec_from_file_location("expert_coverage_report", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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
            post_metadata TEXT
        );
        CREATE TABLE post_embeddings (
            post_id INTEGER PRIMARY KEY
        );
        CREATE TABLE posts_fts (
            content TEXT,
            expert_id TEXT,
            created_at TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO expert_metadata VALUES (?, ?, ?)",
        [
            ("alpha", "Alpha", "alpha_channel"),
            ("beta", "Beta", "beta_channel"),
            ("video_hub", "Video Hub", "video_hub_internal"),
        ],
    )
    alpha_metadata = json.dumps(
        {
            "primary_topic": "AI Agents",
            "concepts": ["MCP", "RAG"],
            "keywords": "claude code, agents, eval, retrieval",
        }
    )
    conn.executemany(
        """
        INSERT INTO posts
        (post_id, expert_id, telegram_message_id, message_text, created_at, post_metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "alpha",
                101,
                "We used Claude Code agents in production with MCP tools and eval benchmark for RAG retrieval.",
                "2026-05-01 10:00:00",
                alpha_metadata,
            ),
            (
                2,
                "beta",
                201,
                "A practical guide to RAG retrieval, embeddings, vector search, and knowledge base design in production.",
                "2026-05-02 10:00:00",
                None,
            ),
            (
                3,
                "video_hub",
                301,
                "Video transcript about AI agents and workflow automation.",
                "2026-05-03 10:00:00",
                None,
            ),
        ],
    )
    conn.executemany("INSERT INTO post_embeddings VALUES (?)", [(1,), (2,), (3,)])
    conn.executemany(
        "INSERT INTO posts_fts(rowid, content, expert_id, created_at) VALUES (?, ?, ?, ?)",
        [
            (1, "alpha fts", "alpha", "2026-05-01"),
            (2, "beta fts", "beta", "2026-05-02"),
            (3, "video fts", "video_hub", "2026-05-03"),
        ],
    )
    return conn


def test_build_report_excludes_video_hub_and_uses_text_when_metadata_missing():
    module = load_module()
    conn = make_db()

    report = module.build_report(
        conn,
        db_path=Path("test.db"),
        include_video_hub=False,
        max_representatives_per_expert=4,
        max_representatives_per_area=2,
    )

    expert_ids = [expert["expert_id"] for expert in report["experts"]]
    assert expert_ids == ["alpha", "beta"]
    assert report["summary"]["expert_count"] == 2

    alpha = next(expert for expert in report["experts"] if expert["expert_id"] == "alpha")
    assert alpha["coverage"]["coding_agents"] >= 1
    assert alpha["coverage"]["agent_ops"] >= 1
    assert alpha["coverage"]["evals_quality"] >= 1
    assert alpha["coverage"]["rag_retrieval_knowledge"] >= 1
    assert alpha["metadata_valid_count"] == 1
    assert alpha["embedding_count"] == 1

    beta = next(expert for expert in report["experts"] if expert["expert_id"] == "beta")
    assert beta["metadata_valid_count"] == 0
    assert beta["coverage"]["rag_retrieval_knowledge"] >= 1
    assert "beta: no valid post_metadata; coverage is text-only" in beta["warnings"]
    assert "beta" in report["gaps"]["experts_without_metadata"]


def test_build_report_ignores_explicit_offtopic_posts():
    module = load_module()
    conn = make_db()
    conn.execute(
        "INSERT INTO expert_metadata VALUES (?, ?, ?)",
        ("gamma", "Gamma", "gamma_channel"),
    )
    conn.execute(
        """
        INSERT INTO posts
        (post_id, expert_id, telegram_message_id, message_text, created_at, post_metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            4,
            "gamma",
            401,
            "#оффтоп product model deployment news with many AI-looking words.",
            "2026-05-04 10:00:00",
            None,
        ),
    )

    report = module.build_report(
        conn,
        db_path=Path("test.db"),
        include_video_hub=False,
    )

    gamma = next(expert for expert in report["experts"] if expert["expert_id"] == "gamma")
    assert not any(gamma["coverage"].values())
    assert gamma["depth_profile"]["low_signal"] == 1
    assert gamma["representative_posts"] == []


def test_build_report_does_not_use_metadata_as_coverage_proof():
    module = load_module()
    conn = make_db()
    conn.execute(
        "INSERT INTO expert_metadata VALUES (?, ?, ?)",
        ("delta", "Delta", "delta_channel"),
    )
    conn.execute(
        """
        INSERT INTO posts
        (post_id, expert_id, telegram_message_id, message_text, created_at, post_metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            4,
            "delta",
            401,
            "A long operational note about meetings and planning without topic keywords.",
            "2026-05-04 10:00:00",
            json.dumps({"concepts": ["RAG", "MCP"], "keywords": "eval benchmark"}),
        ),
    )

    report = module.build_report(
        conn,
        db_path=Path("test.db"),
        include_video_hub=False,
    )

    delta = next(expert for expert in report["experts"] if expert["expert_id"] == "delta")
    assert not any(delta["coverage"].values())
    assert delta["top_concepts"] == [
        {"value": "RAG", "count": 1},
        {"value": "MCP", "count": 1},
    ]


def test_build_report_avoids_broad_search_and_announcement_false_positives():
    module = load_module()
    conn = make_db()
    conn.executemany(
        "INSERT INTO expert_metadata VALUES (?, ?, ?)",
        [
            ("gamma", "Gamma", "gamma_channel"),
            ("delta", "Delta", "delta_channel"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO posts
        (post_id, expert_id, telegram_message_id, message_text, created_at, post_metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                4,
                "gamma",
                401,
                "У Apple неделя анонсов: новые ноутбуки, чипы, камеры и цены для учебных заведений.",
                "2026-05-04 10:00:00",
                None,
            ),
            (
                5,
                "delta",
                501,
                "Поиск подрядчика для проекта занял несколько недель и не связан с базами знаний.",
                "2026-05-04 10:00:00",
                None,
            ),
        ],
    )

    report = module.build_report(
        conn,
        db_path=Path("test.db"),
        include_video_hub=False,
    )

    gamma = next(expert for expert in report["experts"] if expert["expert_id"] == "gamma")
    delta = next(expert for expert in report["experts"] if expert["expert_id"] == "delta")
    assert gamma["coverage"]["general_ai_news"] == 0
    assert delta["coverage"]["rag_retrieval_knowledge"] == 0


def test_write_artifacts_creates_current_report_and_passports(tmp_path):
    module = load_module()
    conn = make_db()
    report = module.build_report(
        conn,
        db_path=Path("test.db"),
        include_video_hub=False,
    )

    module.write_artifacts(report, tmp_path)

    current_json = tmp_path / "current_coverage.json"
    current_md = tmp_path / "current_coverage.md"
    alpha_json = tmp_path / "passports" / "alpha.json"
    alpha_md = tmp_path / "passports" / "alpha.md"

    assert current_json.exists()
    assert current_md.exists()
    assert alpha_json.exists()
    assert alpha_md.exists()

    payload = json.loads(current_json.read_text(encoding="utf-8"))
    assert payload["summary"]["expert_count"] == 2
    assert "Expert Coverage Report" in current_md.read_text(encoding="utf-8")
    assert "Expert Passport: alpha" in alpha_md.read_text(encoding="utf-8")
