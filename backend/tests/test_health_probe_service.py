#!/usr/bin/env python3
"""Unit tests for cached health probes."""

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.services.health_probe_service import HealthProbeService
from src.services.vertex_llm_client import VertexLLMError


class _FakeChoiceMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeChoiceMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class FakeLLMClient:
    def __init__(self, failure_by_model: dict[str, Exception] | None = None):
        self.failure_by_model = failure_by_model or {}
        self.calls: list[str] = []

    async def chat_completions_create(self, model: str, **_: object):
        self.calls.append(model)
        if model in self.failure_by_model:
            raise self.failure_by_model[model]
        return _FakeResponse("OK")


class FakeEmbeddingService:
    def __init__(self, dimensions: int | None = None, exc: Exception | None = None):
        self.dimensions = dimensions if dimensions is not None else config.EMBEDDING_DIMENSIONS
        self.exc = exc
        self.calls = 0

    async def embed_text(self, text: str, task_type: str = "RETRIEVAL_QUERY"):
        self.calls += 1
        if self.exc:
            raise self.exc
        return [0.1] * self.dimensions


class FakeAuthManager:
    def __init__(
        self,
        configured: bool = True,
        project_id: str | None = "demo-project",
        location: str = "us-central1",
        source: str | None = "test_credentials",
    ):
        self._configured = configured
        self.configured_project_id = project_id
        self.location = location
        self.source = source

    def is_configured(self) -> bool:
        return self._configured


class FactoryCounter:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


@pytest.mark.asyncio
async def test_refresh_summary_reports_generation_embedding_and_availability():
    service = HealthProbeService(
        llm_client=FakeLLMClient(),
        embedding_service=FakeEmbeddingService(),
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
    )

    summary = await service.refresh_summary(force=True)

    assert summary["vertex_auth"]["configured"] is True
    assert summary["generation_probe"]["status"] == "ok"
    assert summary["embedding_probe"]["status"] == "ok"
    assert summary["model_availability"][config.MODEL_MAP]["status"] == "available"
    assert summary["model_availability"][config.MODEL_SYNTHESIS]["route_type"] == "global"
    assert summary["model_availability"][config.MODEL_EMBEDDING]["status"] == "available"


@pytest.mark.asyncio
async def test_refresh_summary_marks_unavailable_generation_models():
    target_model = config.MODEL_MAP
    service = HealthProbeService(
        llm_client=FakeLLMClient(
            failure_by_model={
                target_model: RuntimeError("Error code: 404 - Model not found"),
            }
        ),
        embedding_service=FakeEmbeddingService(),
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
        generation_model=target_model,
    )

    summary = await service.refresh_summary(force=True)

    assert summary["generation_probe"]["status"] == "failed"
    assert summary["generation_probe"]["error_type"] == "model_unavailable"
    assert summary["model_availability"][target_model]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_refresh_summary_reuses_fresh_cache_without_extra_network_calls():
    fake_llm = FakeLLMClient()
    fake_embeddings = FakeEmbeddingService()
    service = HealthProbeService(
        llm_client=fake_llm,
        embedding_service=fake_embeddings,
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
    )

    await service.refresh_summary(force=True)
    llm_calls_after_first_refresh = len(fake_llm.calls)
    embedding_calls_after_first_refresh = fake_embeddings.calls

    await service.refresh_summary(force=False)

    assert len(fake_llm.calls) == llm_calls_after_first_refresh
    assert fake_embeddings.calls == embedding_calls_after_first_refresh


@pytest.mark.asyncio
async def test_get_cached_summary_without_auth_returns_cached_auth_failure_without_client_init():
    llm_factory = FactoryCounter(FakeLLMClient())
    embedding_factory = FactoryCounter(FakeEmbeddingService())
    service = HealthProbeService(
        auth_manager=FakeAuthManager(configured=False, project_id=None, source=None),
        llm_client_factory=llm_factory,
        embedding_service_factory=embedding_factory,
        cache_ttl_seconds=300,
    )

    summary = await service.get_cached_summary()

    assert summary["cache"]["checked_at"] is not None
    assert summary["cache"]["stale"] is False
    assert summary["vertex_auth"]["configured"] is False
    assert summary["generation_probe"]["status"] == "failed"
    assert summary["generation_probe"]["error_type"] == "auth_error"
    assert summary["embedding_probe"]["status"] == "failed"
    assert llm_factory.calls == 0
    assert embedding_factory.calls == 0


@pytest.mark.asyncio
async def test_warm_cache_populates_fresh_summary_when_auth_is_configured():
    fake_llm = FakeLLMClient()
    fake_embeddings = FakeEmbeddingService()
    service = HealthProbeService(
        llm_client=fake_llm,
        embedding_service=fake_embeddings,
        auth_manager=FakeAuthManager(),
        cache_ttl_seconds=300,
    )

    summary = await service.warm_cache()

    assert summary["cache"]["checked_at"] is not None
    assert summary["cache"]["stale"] is False
    assert summary["generation_probe"]["status"] == "ok"
    assert summary["embedding_probe"]["status"] == "ok"
    assert len(fake_llm.calls) >= 1
    assert fake_embeddings.calls == 1


def test_classify_exception_preserves_runtime_error_type():
    service = HealthProbeService(
        llm_client=FakeLLMClient(),
        embedding_service=FakeEmbeddingService(),
        auth_manager=FakeAuthManager(),
    )

    auth_error = service._classify_exception(
        VertexLLMError(
            "Vertex AI credentials are not configured",
            error_type="authentication",
        )
    )
    rate_limit_error = service._classify_exception(
        VertexLLMError(
            "Error code: 429 - quota exceeded",
            error_type="rate_limit",
            is_rate_limit=True,
        )
    )

    assert auth_error["error_type"] == "auth_error"
    assert rate_limit_error["error_type"] == "rate_limit"
    assert rate_limit_error["status_code"] == 429
