#!/usr/bin/env python3
"""Unit tests for the startup-time critical-models availability helper.

The helper is wired into the FastAPI lifespan startup hook in
``backend/src/api/main.py`` so a broken ``MODEL_*`` env var is surfaced
at boot instead of silently degrading the first user query.

These tests cover the fail-open contract: never raises; logs WARNING for
unreachable models; INFO-only on the happy path; bounded by an outer
``asyncio.wait_for`` timeout so a slow Vertex cannot stall startup.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault(
    "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}"
)
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

# Reuse the resilient fakes from the existing probe test suite.
from tests.test_health_probe_service import (  # noqa: E402
    FakeAuthManager,
    FakeEmbeddingService,
    FakeLLMClient,
)
from src import config  # noqa: E402
from src.services import health_probe_service as probe_module  # noqa: E402
from src.services.health_probe_service import (  # noqa: E402
    HealthProbeService,
    log_critical_models_availability,
)


@pytest.fixture(autouse=True)
def _reset_probe_singleton():
    """Snapshot the singleton before each test, restore after.

    The helper resolves the singleton via ``get_health_probe_service()``
    so tests that inject a fake must restore the original to avoid
    cross-test pollution (otherwise subsequent test files can pick up
    a leaked FakeLLMClient).
    """
    original = probe_module._probe_service_instance
    probe_module._probe_service_instance = None
    try:
        yield
    finally:
        probe_module._probe_service_instance = original


@pytest.fixture
def patch_auth_manager(monkeypatch):
    """Swaps ``get_vertex_ai_auth_manager`` so the helper sees a fake manager.

    The helper imports and calls ``get_vertex_ai_auth_manager`` directly at
    runtime, so injecting an unauthenticated FakeAuthManager via the
    HealthProbeService constructor is not enough -- this fixture patches the
    module-level binding that the helper actually uses.
    """

    def _patch(fake: FakeAuthManager) -> None:
        monkeypatch.setattr(
            probe_module, "get_vertex_ai_auth_manager", lambda: fake
        )

    return _patch


@pytest.mark.asyncio
async def test_returns_empty_dict_and_skips_probe_when_auth_not_configured(
    caplog: pytest.LogCaptureFixture, patch_auth_manager
):
    """If Vertex auth is missing, helper must short-circuit with INFO and
    not call the LLM client or raise."""

    captured_clients: List[FakeLLMClient] = []

    def factory() -> FakeLLMClient:
        client = FakeLLMClient()
        captured_clients.append(client)
        return client

    service = HealthProbeService(
        auth_manager=FakeAuthManager(configured=False, project_id=None, source=None),
        llm_client_factory=factory,
        embedding_service_factory=lambda: FakeEmbeddingService(),
        cache_ttl_seconds=300,
    )
    probe_module._probe_service_instance = service
    patch_auth_manager(
        FakeAuthManager(configured=False, project_id=None, source=None)
    )

    with caplog.at_level(logging.INFO):
        result = await log_critical_models_availability(logging.getLogger("test"))

    assert result == {}
    assert captured_clients == [], "LLM client should not be invoked without auth"
    assert any(
        "skipping critical-model availability check" in rec.message
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_logs_warning_when_one_model_returns_404(
    caplog: pytest.LogCaptureFixture, patch_auth_manager
):
    """A single 404 on MODEL_SCOUT must surface as a WARNING with the
    model name, error_type=model_unavailable, and a remediation hint."""

    service = HealthProbeService(
        llm_client=FakeLLMClient(
            failure_by_model={
                config.MODEL_SCOUT: RuntimeError(
                    "Error code: 404 - Publisher Model ...models/"
                    "gemini-3.1-flash-lite-preview was not found"
                ),
            }
        ),
        embedding_service=FakeEmbeddingService(),
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
        generation_model=config.MODEL_SCOUT,
    )
    probe_module._probe_service_instance = service
    patch_auth_manager(FakeAuthManager())

    with caplog.at_level(logging.WARNING):
        result = await log_critical_models_availability(logging.getLogger("test"))

    assert result.get(config.MODEL_SCOUT) == "unavailable"
    warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any(config.MODEL_SCOUT in rec.message for rec in warnings), (
        "Expected a WARNING that names MODEL_SCOUT"
    )
    assert any("model garden" in rec.message for rec in warnings), (
        "Expected remediation hint (reference to Vertex AI model garden)"
    )


@pytest.mark.asyncio
async def test_logs_warning_for_each_unavailable_model(
    caplog: pytest.LogCaptureFixture, patch_auth_manager
):
    """Multiple unreachable models must each emit a separate WARNING."""

    broken_models = {
        config.MODEL_SCOUT: RuntimeError("Error code: 404 - not found"),
        config.MODEL_VIDEO_PRO: RuntimeError("Error code: 404 - not found"),
    }

    service = HealthProbeService(
        llm_client=FakeLLMClient(failure_by_model=broken_models),
        embedding_service=FakeEmbeddingService(),
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
    )
    probe_module._probe_service_instance = service
    patch_auth_manager(FakeAuthManager())

    with caplog.at_level(logging.WARNING):
        result = await log_critical_models_availability(logging.getLogger("test"))

    assert result.get(config.MODEL_SCOUT) == "unavailable"
    assert result.get(config.MODEL_VIDEO_PRO) == "unavailable"

    warning_messages = " ".join(
        rec.message for rec in caplog.records if rec.levelno == logging.WARNING
    )
    assert config.MODEL_SCOUT in warning_messages
    assert config.MODEL_VIDEO_PRO in warning_messages


@pytest.mark.asyncio
async def test_no_warning_on_happy_path(
    caplog: pytest.LogCaptureFixture, patch_auth_manager
):
    """When all tracked models succeed, the helper must NOT emit WARNING
    (avoids log spam when running normally in production)."""

    service = HealthProbeService(
        llm_client=FakeLLMClient(),
        embedding_service=FakeEmbeddingService(),
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
    )
    probe_module._probe_service_instance = service
    patch_auth_manager(FakeAuthManager())

    with caplog.at_level(logging.WARNING):
        result = await log_critical_models_availability(logging.getLogger("test"))

    assert result, "Helper should populate result dict on happy path"
    assert all(status == "available" for status in result.values()), result
    warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert not warnings, (
        f"Happy path must not emit WARNING, got: {[r.message for r in warnings]}"
    )


@pytest.mark.asyncio
async def test_does_not_raise_when_probe_throws(
    caplog: pytest.LogCaptureFixture, patch_auth_manager
):
    """If the underlying probe throws, the helper must swallow it, log a
    WARNING, and return an empty dict -- never break startup."""

    class _BrokenService:
        async def warm_cache(self) -> Dict[str, Any]:
            raise RuntimeError("simulated infra outage")

    probe_module._probe_service_instance = _BrokenService()  # type: ignore[assignment]
    patch_auth_manager(FakeAuthManager())

    with caplog.at_level(logging.WARNING):
        result = await log_critical_models_availability(logging.getLogger("test"))

    assert result == {}
    assert any(
        "availability probe failed at startup" in rec.message
        for rec in caplog.records
    )


@pytest.mark.asyncio
async def test_does_not_raise_and_returns_empty_on_timeout(
    caplog: pytest.LogCaptureFixture, patch_auth_manager
):
    """If Vertex is slow / cold-starting, the helper must time out cleanly
    via its outer ``asyncio.wait_for`` and return ``{}`` -- never block
    FastAPI startup indefinitely."""

    class _SlowService:
        async def warm_cache(self) -> Dict[str, Any]:
            await asyncio.sleep(5)  # cancelled by asyncio.wait_for
            return {"model_availability": {}}  # pragma: no cover

    probe_module._probe_service_instance = _SlowService()  # type: ignore[assignment]
    patch_auth_manager(FakeAuthManager())

    with caplog.at_level(logging.WARNING):
        # 0.5s is generous enough to survive event-loop scheduling lag on
        # busy CI runners while still short enough to keep the test fast.
        result = await log_critical_models_availability(
            logging.getLogger("test"), timeout_seconds=0.5
        )

    assert result == {}
    assert any("timed out" in rec.message for rec in caplog.records)


def test_exports_include_helper() -> None:
    """The helper must be exposed via ``__all__`` for explicit imports."""

    assert "log_critical_models_availability" in probe_module.__all__
    assert hasattr(probe_module, "log_critical_models_availability")
