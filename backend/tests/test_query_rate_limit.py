#!/usr/bin/env python3
"""Contract tests for the public query endpoint abuse guards."""

import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.api.main import app
from src.services import query_rate_limit_service as rate_limit_module


@pytest.fixture(autouse=True)
def _clean_guard_state():
    rate_limit_module.reset_rate_limit_state()
    yield
    rate_limit_module.reset_rate_limit_state()


def _make_request(peer: str = "8.8.8.8", forwarded: str = None):
    """Build a minimal Request-like object for resolve_client_ip tests."""

    class _FakeClient:
        host = peer

    class _FakeRequest:
        client = _FakeClient()
        headers = {"x-forwarded-for": forwarded} if forwarded else {}

    return _FakeRequest()


def test_public_peer_xff_is_not_trusted():
    request = _make_request(peer="8.8.8.8", forwarded="198.51.100.7")
    assert rate_limit_module.resolve_client_ip(request) == "8.8.8.8"


def test_proxy_peer_xff_is_trusted():
    request = _make_request(peer="127.0.0.1", forwarded="198.51.100.7, 10.0.0.2")
    assert rate_limit_module.resolve_client_ip(request) == "198.51.100.7"


def test_private_peer_xff_is_trusted():
    request = _make_request(peer="172.18.0.5", forwarded="198.51.100.7")
    assert rate_limit_module.resolve_client_ip(request) == "198.51.100.7"


def test_proxy_peer_without_xff_falls_back_to_peer():
    request = _make_request(peer="127.0.0.1")
    assert rate_limit_module.resolve_client_ip(request) == "127.0.0.1"


def test_malformed_forwarded_header_falls_back_to_peer():
    request = _make_request(peer="127.0.0.1", forwarded="   ,")
    assert rate_limit_module.resolve_client_ip(request) == "127.0.0.1"


def test_rate_limit_allows_requests_under_limit(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 3)

    for _ in range(3):
        rate_limit_module.check_query_rate_limit("198.51.100.7")


def test_rate_limit_raises_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 2)

    rate_limit_module.check_query_rate_limit("198.51.100.7")
    rate_limit_module.check_query_rate_limit("198.51.100.7")

    with pytest.raises(HTTPException) as exc_info:
        rate_limit_module.check_query_rate_limit("198.51.100.7")

    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1


def test_rate_limit_is_per_ip(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 1)

    rate_limit_module.check_query_rate_limit("198.51.100.7")

    with pytest.raises(HTTPException):
        rate_limit_module.check_query_rate_limit("198.51.100.7")

    # A different client IP still has its own budget.
    rate_limit_module.check_query_rate_limit("198.51.100.8")


def test_rate_limit_can_be_disabled(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 1)

    for _ in range(5):
        rate_limit_module.check_query_rate_limit("198.51.100.7")


def test_rate_limit_zero_limit_disables_guard(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 0)

    for _ in range(5):
        rate_limit_module.check_query_rate_limit("198.51.100.7")


def test_daily_budget_counts_requests(monkeypatch):
    monkeypatch.setattr(config, "DAILY_QUERY_BUDGET", 2)

    rate_limit_module.check_and_consume_daily_budget()
    rate_limit_module.check_and_consume_daily_budget()

    with pytest.raises(HTTPException) as exc_info:
        rate_limit_module.check_and_consume_daily_budget()

    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1


def test_daily_budget_resets_on_date_rollover(monkeypatch):
    monkeypatch.setattr(config, "DAILY_QUERY_BUDGET", 1)

    rate_limit_module.check_and_consume_daily_budget()
    with pytest.raises(HTTPException):
        rate_limit_module.check_and_consume_daily_budget()

    rate_limit_module._DAILY_BUDGET_STATE["date"] = "2000-01-01"
    rate_limit_module.check_and_consume_daily_budget()


def test_daily_budget_zero_disables_guard(monkeypatch):
    monkeypatch.setattr(config, "DAILY_QUERY_BUDGET", 0)

    for _ in range(5):
        rate_limit_module.check_and_consume_daily_budget()


def test_query_endpoint_returns_429_when_ip_exhausted(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 1)
    monkeypatch.setattr(config, "DAILY_QUERY_BUDGET", 1_000_000)

    # Exhaust the identity the TestClient will present ("testclient" is not a
    # valid IP, so the guard falls back to the peer string).
    rate_limit_module.check_query_rate_limit("testclient")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/query",
            json={"query": "What does Refat say about agents?", "expert_filter": ["refat"]},
        )

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "Too many queries" in response.json()["message"]


def test_query_endpoint_validation_errors_do_not_consume_budget(monkeypatch):
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "QUERY_RATE_LIMIT_PER_HOUR", 100)
    monkeypatch.setattr(config, "DAILY_QUERY_BUDGET", 1)

    with TestClient(app) as client:
        for _ in range(3):
            response = client.post(
                "/api/v1/query",
                json={"query": "What does Refat say about agents?", "expert_filter": []},
            )
            assert response.status_code == 422

    # The 422 responses must not have burned the daily budget.
    rate_limit_module.check_and_consume_daily_budget()
