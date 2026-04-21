#!/usr/bin/env python3
"""Smoke tests for /health and /health/live."""

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src.api.main import app
from src import config
from src.services import health_probe_service as health_probe_module


def _build_probe_summary() -> dict:
    return {
        "cache": {
            "checked_at": 123.0,
            "expires_at": 423.0,
            "ttl_seconds": 300,
            "stale": False,
            "refresh_in_progress": False,
        },
        "vertex_auth": {
            "configured": True,
            "project_id": "demo-project",
            "location": "us-central1",
            "auth_source": "test_credentials",
        },
        "generation_probe": {
            "ok": True,
            "status": "ok",
            "model": config.MODEL_MAP,
            "route_type": "regional",
            "latency_ms": 12.5,
            "error_type": None,
            "message": None,
            "status_code": None,
        },
        "embedding_probe": {
            "ok": True,
            "status": "ok",
            "model": config.MODEL_EMBEDDING,
            "route_type": "regional",
            "dimensions": config.EMBEDDING_DIMENSIONS,
            "expected_dimensions": config.EMBEDDING_DIMENSIONS,
            "latency_ms": 9.2,
            "error_type": None,
            "message": None,
            "status_code": None,
        },
        "model_availability": {
            config.MODEL_MAP: {
                "status": "available",
                "kind": "generation",
                "route_type": "regional",
                "latency_ms": 12.5,
                "error_type": None,
                "message": None,
                "status_code": None,
                "dimensions": None,
                "expected_dimensions": None,
            },
            config.MODEL_EMBEDDING: {
                "status": "available",
                "kind": "embedding",
                "route_type": "regional",
                "latency_ms": 9.2,
                "error_type": None,
                "message": None,
                "status_code": None,
                "dimensions": config.EMBEDDING_DIMENSIONS,
                "expected_dimensions": config.EMBEDDING_DIMENSIONS,
            },
        },
    }


class FakeHealthProbeService:
    def __init__(self):
        self.cached_calls = 0
        self.live_calls = 0
        self.warm_calls = 0

    async def warm_cache(self):
        self.warm_calls += 1
        return _build_probe_summary()

    async def get_cached_summary(self):
        self.cached_calls += 1
        return _build_probe_summary()

    async def refresh_summary(self, force: bool = False):
        assert force is True
        self.live_calls += 1
        return _build_probe_summary()


def test_health_returns_cached_diagnostics(monkeypatch):
    fake_service = FakeHealthProbeService()
    monkeypatch.setattr(health_probe_module, "get_health_probe_service", lambda: fake_service)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["database"] == "healthy"
    assert payload["auth_configured"] is True
    assert payload["diagnostics"]["mode"] == "cached"
    assert payload["diagnostics"]["generation_probe"]["status"] == "ok"
    assert fake_service.cached_calls == 1
    assert fake_service.warm_calls == 1


def test_health_live_requires_admin_secret(monkeypatch):
    fake_service = FakeHealthProbeService()
    monkeypatch.setattr(health_probe_module, "get_health_probe_service", lambda: fake_service)
    monkeypatch.setenv("ADMIN_SECRET", "top-secret")

    with TestClient(app) as client:
        unauthorized = client.get("/health/live")
        authorized = client.get("/health/live", headers={"X-Admin-Secret": "top-secret"})

    assert unauthorized.status_code == 403, unauthorized.text
    assert authorized.status_code == 200, authorized.text
    payload = authorized.json()
    assert payload["diagnostics"]["mode"] == "live"
    assert payload["diagnostics"]["embedding_probe"]["status"] == "ok"
    assert fake_service.live_calls == 1
    assert fake_service.warm_calls == 1
