"""FastAPI route tests with a mocked orchestrator (no Docker required)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import main
from events import Event
from orchestrator import Job, JobStatus


@pytest.fixture
def client(monkeypatch):
    mock_orch = MagicMock()
    mock_orch.spawn = AsyncMock(return_value="abcdef0123456789")
    mock_orch.cancel = AsyncMock(return_value=True)
    mock_orch.get = MagicMock(return_value=None)
    mock_orch.read_logs = MagicMock(return_value=None)
    monkeypatch.setattr(main, "orchestrator", mock_orch)
    return TestClient(main.app), mock_orch


def test_post_research_empty_query_returns_422(client):
    c, _ = client
    r = c.post("/research", json={"query": ""})
    assert r.status_code == 422


def test_post_research_missing_query_returns_422(client):
    c, _ = client
    r = c.post("/research", json={})
    assert r.status_code == 422


def test_post_research_returns_202_and_job_id(client):
    c, orch = client
    r = c.post("/research", json={"query": "what is RAG"})
    assert r.status_code == 202
    assert r.json() == {
        "job_id": "abcdef0123456789",
        "status": "queued",
        "mode": "standard",
        "max_report_chars": 6000,
        "language": "auto",
    }
    orch.spawn.assert_awaited_once_with(
        query="what is RAG",
        mode="standard",
        max_report_chars=None,
        language="auto",
    )


def test_post_research_accepts_deep_mode_options(client):
    c, orch = client
    r = c.post(
        "/research",
        json={
            "query": "compare hosted search options",
            "mode": "deep",
            "max_report_chars": 16000,
            "language": "ru",
        },
    )
    assert r.status_code == 202
    assert r.json() == {
        "job_id": "abcdef0123456789",
        "status": "queued",
        "mode": "deep",
        "max_report_chars": 16000,
        "language": "ru",
    }
    orch.spawn.assert_awaited_once_with(
        query="compare hosted search options",
        mode="deep",
        max_report_chars=16000,
        language="ru",
    )


def test_post_research_unknown_mode_returns_422(client):
    c, _ = client
    r = c.post("/research", json={"query": "what is RAG", "mode": "quick"})
    assert r.status_code == 422


def test_get_research_unknown_returns_404(client):
    c, orch = client
    orch.get.return_value = None
    r = c.get("/research/deadbeefdeadbeef")
    assert r.status_code == 404


def test_get_research_running_does_not_include_report(client):
    c, orch = client
    orch.get.return_value = Job(id="abc", query="x", status=JobStatus.running)
    r = c.get("/research/abc")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["mode"] == "standard"
    assert body.get("report") is None


def test_get_research_completed_returns_report_content(client):
    c, orch = client
    orch.get.return_value = Job(
        id="abc",
        query="x",
        status=JobStatus.completed,
        report="# Title\n\n[1] src\n",
    )
    r = c.get("/research/abc")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["report"].startswith("# Title")


def test_get_research_timeout_returns_partial_report_and_progress(client, tmp_path):
    c, orch = client
    workspace = tmp_path / "job"
    extracts_dir = workspace / "extracts"
    extracts_dir.mkdir(parents=True)
    (extracts_dir / "source-a.md").write_text("# Source A\n", encoding="utf-8")
    (workspace / "partial_report.md").write_text(
        "# Partial Deep Research Report\n",
        encoding="utf-8",
    )
    job = Job(
        id="abc",
        query="x",
        mode="deep",
        status=JobStatus.timeout,
        workspace_path=workspace,
        partial_report="# Partial Deep Research Report\n",
        error="exceeded timeout of 1200s",
    )
    job.events = [
        Event.now(
            job_id="abc",
            agent_id="lead",
            type="tool_call",
            payload={"title": "delegate task", "id": "call-1"},
        ),
        Event.now(
            job_id="abc",
            agent_id="sub-call-1-1",
            parent_id="lead",
            type="spawn",
            payload={"goal": "Research one branch."},
        ),
        Event.now(
            job_id="abc",
            agent_id="sub-call-1-1",
            parent_id="lead",
            type="done",
            payload={"status": "completed"},
        ),
    ]
    orch.get.return_value = job

    r = c.get("/research/abc")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "timeout"
    assert body["partial_report"].startswith("# Partial")
    assert body["progress"]["phase"] == "partial_timeout"
    assert body["progress"]["delegate_rounds"] == 1
    assert body["progress"]["subagents"]["spawned"] == 1
    assert body["progress"]["subagents"]["status_counts"] == {"completed": 1}
    assert body["progress"]["extracts"]["count"] == 1
    assert body["progress"]["has_partial_report"] is True


def test_delete_research_calls_cancel(client):
    c, orch = client
    orch.get.return_value = Job(id="abc", query="x", status=JobStatus.running)
    r = c.delete("/research/abc")
    assert r.status_code == 200
    orch.cancel.assert_awaited_once_with("abc")
