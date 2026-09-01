#!/usr/bin/env python3
"""Contract tests for the agent-facing Reddit Search V2 API.

Covers the handoff contract in
docs/plans/2026-08-29-reddit-search-agent-api-handoff.md:

- valid query -> completed with structured sources
- too short / too long / empty query -> 400/422
- use_recent_only=true/false accepted
- abstained without being masked as an error
- upstream failure/timeout -> safe 5xx, never a 200 failed
- unauthorized request -> 403
- no stack traces or secret-like values in any response
- proof that the endpoint calls the shared Search V2 logic
  (run_reddit_search_v2), not a copied pipeline
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import os

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.api import dependencies
from src.api.agent_context_endpoint import router as agent_context_router
from src.api.simplified_query_endpoint import (
    RedditSearchV2Outcome,
    run_reddit_search_v2,
)

_ENDPOINT = "/api/v1/agent/reddit-search"


@pytest.fixture(autouse=True)
def reddit_search_test_config(monkeypatch):
    monkeypatch.setattr(config, "AGENT_CONTEXT_API_TOKEN", "valid-agent-token")
    monkeypatch.setattr(
        config, "REDDIT_SEARCH_CLIENT_TOKENS", ["valid-reddit-client-token"]
    )
    monkeypatch.setattr(config, "AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(config, "AGENT_CONTEXT_TIMEOUT_SECONDS", 90)
    monkeypatch.setattr(config, "AGENT_CONTEXT_MAX_RESPONSE_BYTES", 500000)
    dependencies._AGENT_CONTEXT_RATE_LIMIT_BUCKETS.clear()
    yield
    dependencies._AGENT_CONTEXT_RATE_LIMIT_BUCKETS.clear()


def _auth_headers(token: str = "valid-agent-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


def _completed_outcome():
    """A completed V2 run with two real sources and a synthesis."""
    return RedditSearchV2Outcome(
        status="completed",
        response=SimpleNamespace(
            synthesis="Practitioners say hooks are powerful.",
            sources=[
                SimpleNamespace(
                    title="Claude Code hooks changed my workflow",
                    url="https://www.reddit.com/r/ClaudeAI/comments/abc1/hooks/",
                    subreddit="ClaudeAI",
                ),
                SimpleNamespace(
                    title="MCP vs hooks comparison",
                    url="https://www.reddit.com/r/mcp/comments/def2/mcp_vs_hooks/",
                    subreddit="mcp",
                ),
            ],
            found_count=2,
        ),
    )


@pytest.fixture()
def mock_pipeline(monkeypatch):
    """Point run_reddit_search_v2 at a controllable fake and record calls."""
    calls = []

    async def fake_run(query, recent_only=False):
        calls.append({"query": query, "recent_only": recent_only})
        return _completed_outcome()

    monkeypatch.setattr(
        "src.api.agent_context_endpoint.run_reddit_search_v2", fake_run
    )
    return calls


def _post(client, monkeypatch, *, token="valid-agent-token", **payload):
    body = {"query": "What do practitioners say about Claude Code hooks?"}
    body.update(payload)
    headers = _auth_headers(token) if token is not None else None
    return client.post(_ENDPOINT, headers=headers, json=body)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_reddit_search_missing_token_returns_403():
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT, json={"query": "What do practitioners say about hooks?"}
        )
    assert response.status_code == 403, response.text
    assert "token" in response.json()["message"].lower()


def test_reddit_search_wrong_token_returns_403():
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers("wrong-token"),
            json={"query": "What do practitioners say about hooks?"},
        )
    assert response.status_code == 403, response.text


def test_reddit_search_dedicated_client_token_is_accepted(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = _post(
            client,
            None,
            token="valid-reddit-client-token",
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


def test_reddit_client_token_does_not_grant_agent_context_access():
    with pytest.raises(Exception) as exc_info:
        dependencies.verify_agent_context_token(
            authorization="Bearer valid-reddit-client-token"
        )

    assert getattr(exc_info.value, "status_code", None) == 403


def test_reddit_search_without_any_configured_token_returns_500(monkeypatch):
    from src.api.main import app

    monkeypatch.setattr(config, "AGENT_CONTEXT_API_TOKEN", None)
    monkeypatch.setattr(config, "REDDIT_SEARCH_CLIENT_TOKENS", [])
    with TestClient(app) as client:
        response = _post(client, monkeypatch, token="any-token")

    assert response.status_code == 500, response.text
    assert "reddit search api token" in response.json()["message"].lower()


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


def test_reddit_search_empty_query_returns_422(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(_ENDPOINT, headers=_auth_headers(), json={"query": ""})
    assert response.status_code == 422, response.text
    assert response.json()["error"] == "validation_error", response.text


def test_reddit_search_too_short_query_returns_422(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(_ENDPOINT, headers=_auth_headers(), json={"query": "hi"})
    assert response.status_code == 422, response.text


def test_reddit_search_too_long_query_returns_422(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT, headers=_auth_headers(), json={"query": "x" * 1001}
        )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Completed / abstained
# ---------------------------------------------------------------------------


def test_reddit_search_completed_returns_structured_sources(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={
                "query": "What do practitioners say about Claude Code hooks?",
                "use_recent_only": False,
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["query"] == "What do practitioners say about Claude Code hooks?"
    assert payload["answer"] == "Practitioners say hooks are powerful."
    assert payload["message"] is None
    assert payload["found_count"] == 2
    assert len(payload["sources"]) == 2
    for src in payload["sources"]:
        assert set(src) == {"title", "url", "subreddit"}
        assert src["url"].startswith("https://www.reddit.com/r/")
    # proof the endpoint routes through the shared V2 wrapper
    assert mock_pipeline == [
        {
            "query": "What do practitioners say about Claude Code hooks?",
            "recent_only": False,
        }
    ]


def test_reddit_search_use_recent_only_is_forwarded(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={
                "query": "What changed in local LLMs recently?",
                "use_recent_only": True,
            },
        )

    assert response.status_code == 200, response.text
    assert mock_pipeline[0]["recent_only"] is True


def test_reddit_search_abstained_is_not_masked_as_error(monkeypatch):
    from src.api.main import app

    async def fake_abstain(query, recent_only=False):
        return RedditSearchV2Outcome(status="abstained")

    monkeypatch.setattr(
        "src.api.agent_context_endpoint.run_reddit_search_v2", fake_abstain
    )

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={"query": "Obscure query with no reddit results"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "abstained"
    assert payload["answer"] is None
    assert payload["sources"] == []
    assert payload["message"]
    assert "failed" not in payload["status"]


# ---------------------------------------------------------------------------
# Technical failures
# ---------------------------------------------------------------------------


def test_reddit_search_upstream_failure_returns_safe_5xx(monkeypatch):
    from src.api.main import app

    async def fake_failed(query, recent_only=False):
        raise RuntimeError(
            "Reddit proxy connection refused at http://reddit-proxy:3000 (secret=abc)"
        )

    monkeypatch.setattr(
        "src.api.agent_context_endpoint.run_reddit_search_v2", fake_failed
    )

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={"query": "What do practitioners say about hooks?"},
        )

    assert 500 <= response.status_code < 600, response.text
    body = response.text
    assert "failed" not in response.json().get("status", ""), response.text
    assert "Reddit Search API request failed" in body
    assert "secret=abc" not in body, body
    assert "reddit-proxy:3000" not in body, body


def test_reddit_search_timeout_returns_504(monkeypatch):
    from src.api.main import app

    async def fake_hang(query, recent_only=False):
        import asyncio

        await asyncio.sleep(3600)

    monkeypatch.setattr(
        "src.api.agent_context_endpoint.run_reddit_search_v2", fake_hang
    )
    monkeypatch.setattr(config, "AGENT_CONTEXT_TIMEOUT_SECONDS", 1)

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={"query": "What do practitioners say about hooks?"},
        )

    assert response.status_code == 504, response.text
    body = response.text
    assert "timeout" in body.lower()


def test_reddit_search_invalid_timeout_config_returns_500(monkeypatch):
    from src.api.main import app

    monkeypatch.setattr(config, "AGENT_CONTEXT_TIMEOUT_SECONDS", 0)

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={"query": "What do practitioners say about hooks?"},
        )

    assert response.status_code == 500, response.text
    assert "AGENT_CONTEXT_TIMEOUT_SECONDS must be positive" in response.text


# ---------------------------------------------------------------------------
# Secret / stack-trace hygiene
# ---------------------------------------------------------------------------


def test_reddit_search_error_response_has_no_stack_trace(monkeypatch):
    from src.api.main import app

    async def fake_boom(query, recent_only=False):
        try:
            raise ValueError("internal detail with token=sk-live-12345")
        except ValueError:
            raise

    monkeypatch.setattr(
        "src.api.agent_context_endpoint.run_reddit_search_v2", fake_boom
    )

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={"query": "What do practitioners say about hooks?"},
        )

    assert 500 <= response.status_code < 600, response.text
    body = response.text
    assert "Traceback" not in body, body
    assert "sk-live-12345" not in body, body
    assert ".py" not in body, body


def test_reddit_search_success_response_has_no_secrets(mock_pipeline):
    from src.api.main import app

    with TestClient(app) as client:
        response = client.post(
            _ENDPOINT,
            headers=_auth_headers(),
            json={"query": "What do practitioners say about hooks?"},
        )

    assert response.status_code == 200, response.text
    body = response.text
    assert "valid-agent-token" not in body, body
    assert "Bearer" not in body, body
