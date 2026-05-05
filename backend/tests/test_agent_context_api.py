#!/usr/bin/env python3
"""Targeted tests for the Agent Context API MVP skeleton."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.api import dependencies
from src.api.main import app
from src.services import health_probe_service as health_probe_module


class FakeHealthProbeService:
    async def warm_cache(self):
        return {}


@pytest.fixture(autouse=True)
def agent_context_test_config(monkeypatch):
    fake_service = FakeHealthProbeService()
    monkeypatch.setattr(
        health_probe_module,
        "get_health_probe_service",
        lambda: fake_service,
    )
    monkeypatch.setattr(config, "AGENT_CONTEXT_API_TOKEN", "valid-agent-token")
    monkeypatch.setattr(config, "AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(config, "AGENT_CONTEXT_TIMEOUT_SECONDS", 90)
    monkeypatch.setattr(config, "AGENT_CONTEXT_MAX_RESPONSE_BYTES", 500000)
    dependencies._AGENT_CONTEXT_RATE_LIMIT_BUCKETS.clear()
    yield
    dependencies._AGENT_CONTEXT_RATE_LIMIT_BUCKETS.clear()


def _agent_context_payload(**overrides):
    payload = {
        "query": "Что Refat и Akimov писали про AI agents для отдела продаж?",
        "response_mode": "source_bundle",
        "expert_scope": "custom",
        "expert_filter": ["refat", "akimov"],
    }
    payload.update(overrides)
    return payload


def _auth_headers(token: str = "valid-agent-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_agent_context_missing_token_returns_403():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            json=_agent_context_payload(),
        )

    assert response.status_code == 403, response.text
    assert response.json()["message"] == "Invalid agent context token"


def test_agent_context_wrong_token_returns_403():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers("wrong-token"),
            json=_agent_context_payload(),
        )

    assert response.status_code == 403, response.text
    assert response.json()["message"] == "Invalid agent context token"


def test_agent_context_unconfigured_token_returns_500(monkeypatch):
    monkeypatch.setattr(config, "AGENT_CONTEXT_API_TOKEN", None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(),
        )

    assert response.status_code == 500, response.text
    assert response.json()["message"] == "AGENT_CONTEXT_API_TOKEN is not configured"


def test_agent_context_valid_token_reaches_endpoint_skeleton():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(),
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "source_bundle"
    assert payload["query"] == _agent_context_payload()["query"]
    assert payload["experts"] == []
    assert payload["selection_used"] == {
        "expert_scope": "custom",
        "expert_group": None,
        "expert_filter": ["refat", "akimov"],
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": False,
    }
    assert "agent_context_auth" in payload["pipeline_used"]
    assert "reduce_answer_synthesis" in payload["pipeline_skipped"]
    assert payload["warnings"] == ["agent_context_source_pipeline_not_implemented"]


def test_agent_context_rate_limit_exceeded_returns_429(monkeypatch):
    monkeypatch.setattr(config, "AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE", 1)

    with TestClient(app) as client:
        first_response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(),
        )
        second_response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(),
        )

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 429, second_response.text
    assert second_response.json()["message"] == "Agent Context API rate limit exceeded"


def test_existing_query_endpoint_route_remains_registered():
    query_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/query"
    ]

    assert query_routes, "Expected existing /api/v1/query route to stay registered"
    assert any("POST" in getattr(route, "methods", set()) for route in query_routes)
    assert any(
        getattr(route, "endpoint", None).__name__ == "process_simplified_query"
        for route in query_routes
    )
