"""Cached health probes for runtime diagnostics.

This service keeps the expensive Vertex checks out of ``main.py`` and provides:
- cached generation probe
- cached embedding probe
- model availability summary
- auth/project/location diagnostics
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import re
import time
from typing import Any, Callable, Dict, Optional

from .. import config
from ..utils.api_error_detector import APIErrorDetector, ErrorType
from .embedding_service import EmbeddingService, get_embedding_service
from .vertex_ai_auth import VertexAIAuthManager, get_vertex_ai_auth_manager
from .vertex_llm_client import VertexLLMClient, get_vertex_llm_client

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_TTL_SECONDS = max(30, int(os.getenv("HEALTH_PROBE_TTL_SECONDS", "300")))
_DEFAULT_GENERATION_MODEL = os.getenv("HEALTH_GENERATION_MODEL", config.MODEL_MAP)
_GENERATION_PROMPT = "Respond with OK only."
_EMBEDDING_PROBE_TEXT = "health probe"
_STATUS_CODE_RE = re.compile(r"Error code:\s*(\d+)")


def _unique_models(*values: str) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


class HealthProbeService:
    """TTL-cached runtime probes for health endpoints and maintenance tooling."""

    def __init__(
        self,
        llm_client: Optional[VertexLLMClient] = None,
        embedding_service: Optional[EmbeddingService] = None,
        auth_manager: Optional[VertexAIAuthManager] = None,
        llm_client_factory: Optional[Callable[[], VertexLLMClient]] = None,
        embedding_service_factory: Optional[Callable[[], EmbeddingService]] = None,
        auth_manager_factory: Optional[Callable[[], VertexAIAuthManager]] = None,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
        generation_model: str = _DEFAULT_GENERATION_MODEL,
        time_fn: Callable[[], float] = time.time,
    ):
        self._llm_client = llm_client
        self._embedding_service = embedding_service
        self._auth_manager = auth_manager
        self._llm_client_factory = llm_client_factory or get_vertex_llm_client
        self._embedding_service_factory = (
            embedding_service_factory or get_embedding_service
        )
        self._auth_manager_factory = auth_manager_factory or get_vertex_ai_auth_manager
        self._cache_ttl_seconds = cache_ttl_seconds
        self._generation_model = generation_model or config.MODEL_MAP
        self._time_fn = time_fn
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: Optional[asyncio.Task[None]] = None
        self._tracked_generation_models = _unique_models(
            self._generation_model,
            config.MODEL_MAP,
            config.MODEL_SYNTHESIS,
            config.MODEL_ANALYSIS,
            config.MODEL_SCOUT,
            config.MODEL_MEDIUM_SCORING,
            config.MODEL_COMMENT_GROUPS,
            config.MODEL_DRIFT_ANALYSIS,
            config.MODEL_META_SYNTHESIS,
            config.MODEL_VIDEO_PRO,
            config.MODEL_VIDEO_FLASH,
        )
        self._cached_summary = self._build_empty_summary()

    async def get_cached_summary(self) -> Dict[str, Any]:
        """Return the current cached summary and trigger async refresh when stale."""
        if self._is_stale(self._cached_summary):
            await self.warm_cache()
        return self._snapshot(self._cached_summary)

    async def warm_cache(self) -> Dict[str, Any]:
        """Populate auth diagnostics and prime the cached probe state."""
        if not self._is_stale(self._cached_summary):
            return self._snapshot(self._cached_summary)

        auth_summary = self._build_auth_summary()
        self._cached_summary["vertex_auth"] = auth_summary
        return await self.refresh_summary(force=True)

    async def refresh_summary(self, force: bool = False) -> Dict[str, Any]:
        """Refresh all probes unless the current cache is still fresh."""
        if not force and not self._is_stale(self._cached_summary):
            return self._snapshot(self._cached_summary)

        async with self._refresh_lock:
            if not force and not self._is_stale(self._cached_summary):
                return self._snapshot(self._cached_summary)

            summary = await self._build_summary()
            self._cached_summary = summary
            return self._snapshot(summary)

    def _build_empty_summary(self) -> Dict[str, Any]:
        return {
            "cache": {
                "checked_at": None,
                "expires_at": None,
                "ttl_seconds": self._cache_ttl_seconds,
                "stale": True,
                "refresh_in_progress": False,
            },
            "vertex_auth": {
                "configured": False,
                "project_id": config.VERTEX_AI_PROJECT_ID,
                "location": config.VERTEX_AI_LOCATION,
                "auth_source": None,
            },
            "generation_probe": self._unknown_generation_probe(self._generation_model),
            "embedding_probe": self._unknown_embedding_probe(),
            "model_availability": self._unknown_model_availability(),
        }

    async def _build_summary(self) -> Dict[str, Any]:
        checked_at = self._time_fn()
        auth_summary = self._build_auth_summary()

        if not auth_summary["configured"]:
            generation_probe = self._auth_failure_generation_probe(self._generation_model)
            embedding_probe = self._auth_failure_embedding_probe()
            model_availability = self._unknown_model_availability(
                error_type="auth_error",
                message="Vertex AI credentials are not configured",
            )
        else:
            generation_probe, embedding_probe = await asyncio.gather(
                self._run_generation_probe(self._generation_model),
                self._run_embedding_probe(),
            )
            model_availability = await self._build_model_availability(
                generation_probe=generation_probe,
                embedding_probe=embedding_probe,
            )

        return {
            "cache": {
                "checked_at": checked_at,
                "expires_at": checked_at + self._cache_ttl_seconds,
                "ttl_seconds": self._cache_ttl_seconds,
                "stale": False,
                "refresh_in_progress": False,
            },
            "vertex_auth": auth_summary,
            "generation_probe": generation_probe,
            "embedding_probe": embedding_probe,
            "model_availability": model_availability,
        }

    def _build_auth_summary(self) -> Dict[str, Any]:
        auth_manager = self._get_auth_manager()
        return {
            "configured": auth_manager.is_configured(),
            "project_id": auth_manager.configured_project_id,
            "location": auth_manager.location,
            "auth_source": auth_manager.source,
        }

    def _snapshot(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = copy.deepcopy(summary)
        snapshot["cache"]["stale"] = self._is_stale(summary)
        snapshot["cache"]["refresh_in_progress"] = bool(
            self._refresh_task and not self._refresh_task.done()
        )
        return snapshot

    def _is_stale(self, summary: Dict[str, Any]) -> bool:
        expires_at = summary.get("cache", {}).get("expires_at")
        if not expires_at:
            return True
        return self._time_fn() >= expires_at

    def _route_type_for_model(self, model: str) -> str:
        return "global" if model.startswith("gemini-3") else "regional"

    async def _run_generation_probe(self, model: str) -> Dict[str, Any]:
        started_at = time.perf_counter()
        try:
            response = await self._get_llm_client().chat_completions_create(
                model=model,
                messages=[{"role": "user", "content": _GENERATION_PROMPT}],
                temperature=0,
                max_tokens=8,
            )
            response_text = response.choices[0].message.content.strip()
            ok = response_text.upper().startswith("OK")
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            result = {
                "ok": ok,
                "status": "ok" if ok else "failed",
                "model": model,
                "route_type": self._route_type_for_model(model),
                "latency_ms": latency_ms,
                "error_type": None,
                "message": None,
                "status_code": None,
            }
            if not ok:
                result["error_type"] = "invalid_response"
                result["message"] = f"Unexpected probe response: {response_text[:120]}"
            return result
        except Exception as exc:
            details = self._classify_exception(exc)
            return {
                "ok": False,
                "status": "failed",
                "model": model,
                "route_type": self._route_type_for_model(model),
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                **details,
            }

    async def _run_embedding_probe(self) -> Dict[str, Any]:
        started_at = time.perf_counter()
        try:
            vector = await self._get_embedding_service().embed_text(
                _EMBEDDING_PROBE_TEXT,
                task_type="RETRIEVAL_QUERY",
            )
            dimensions = len(vector)
            ok = dimensions == config.EMBEDDING_DIMENSIONS
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            result = {
                "ok": ok,
                "status": "ok" if ok else "failed",
                "model": config.MODEL_EMBEDDING,
                "route_type": "regional",
                "dimensions": dimensions,
                "expected_dimensions": config.EMBEDDING_DIMENSIONS,
                "latency_ms": latency_ms,
                "error_type": None,
                "message": None,
                "status_code": None,
            }
            if not ok:
                result["error_type"] = "invalid_dimensions"
                result["message"] = (
                    f"Expected {config.EMBEDDING_DIMENSIONS} dimensions, got {dimensions}"
                )
            return result
        except Exception as exc:
            details = self._classify_exception(exc)
            return {
                "ok": False,
                "status": "failed",
                "model": config.MODEL_EMBEDDING,
                "route_type": "regional",
                "dimensions": None,
                "expected_dimensions": config.EMBEDDING_DIMENSIONS,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                **details,
            }

    async def _build_model_availability(
        self,
        generation_probe: Dict[str, Any],
        embedding_probe: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        availability: Dict[str, Dict[str, Any]] = {}

        for model in self._tracked_generation_models:
            if model == generation_probe["model"]:
                probe_result = generation_probe
            else:
                probe_result = await self._run_generation_probe(model)
            availability[model] = self._availability_from_probe(
                probe_result,
                kind="generation",
            )

        availability[config.MODEL_EMBEDDING] = self._availability_from_probe(
            embedding_probe,
            kind="embedding",
        )
        return availability

    def _availability_from_probe(
        self,
        probe_result: Dict[str, Any],
        kind: str,
    ) -> Dict[str, Any]:
        status = "available"
        if not probe_result["ok"]:
            if probe_result.get("status_code") == 404 or probe_result.get("error_type") == "model_unavailable":
                status = "unavailable"
            else:
                status = "unknown"

        return {
            "status": status,
            "kind": kind,
            "route_type": probe_result.get("route_type"),
            "latency_ms": probe_result.get("latency_ms"),
            "error_type": probe_result.get("error_type"),
            "message": probe_result.get("message"),
            "status_code": probe_result.get("status_code"),
            "dimensions": probe_result.get("dimensions"),
            "expected_dimensions": probe_result.get("expected_dimensions"),
        }

    def _unknown_generation_probe(self, model: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "status": "unknown",
            "model": model,
            "route_type": self._route_type_for_model(model),
            "latency_ms": None,
            "error_type": None,
            "message": "Probe has not been executed yet",
            "status_code": None,
        }

    def _unknown_embedding_probe(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "status": "unknown",
            "model": config.MODEL_EMBEDDING,
            "route_type": "regional",
            "dimensions": None,
            "expected_dimensions": config.EMBEDDING_DIMENSIONS,
            "latency_ms": None,
            "error_type": None,
            "message": "Probe has not been executed yet",
            "status_code": None,
        }

    def _auth_failure_generation_probe(self, model: str) -> Dict[str, Any]:
        probe = self._unknown_generation_probe(model)
        probe.update(
            {
                "status": "failed",
                "error_type": "auth_error",
                "message": "Vertex AI credentials are not configured",
            }
        )
        return probe

    def _auth_failure_embedding_probe(self) -> Dict[str, Any]:
        probe = self._unknown_embedding_probe()
        probe.update(
            {
                "status": "failed",
                "error_type": "auth_error",
                "message": "Vertex AI credentials are not configured",
            }
        )
        return probe

    def _unknown_model_availability(
        self,
        error_type: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        availability: Dict[str, Dict[str, Any]] = {}
        for model in self._tracked_generation_models:
            availability[model] = {
                "status": "unknown",
                "kind": "generation",
                "route_type": self._route_type_for_model(model),
                "latency_ms": None,
                "error_type": error_type,
                "message": message,
                "status_code": None,
                "dimensions": None,
                "expected_dimensions": None,
            }
        availability[config.MODEL_EMBEDDING] = {
            "status": "unknown",
            "kind": "embedding",
            "route_type": "regional",
            "latency_ms": None,
            "error_type": error_type,
            "message": message,
            "status_code": None,
            "dimensions": None,
            "expected_dimensions": config.EMBEDDING_DIMENSIONS,
        }
        return availability

    def _classify_exception(self, exc: Exception) -> Dict[str, Any]:
        message = str(exc)
        status_code = self._extract_status_code(exc, message)

        runtime_error_type = self._extract_runtime_error_type(exc)
        if runtime_error_type:
            return {
                "error_type": runtime_error_type,
                "message": message,
                "status_code": status_code,
            }

        status_code_error_type = self._classify_status_code(status_code)
        if status_code_error_type:
            return {
                "error_type": status_code_error_type,
                "message": message,
                "status_code": status_code,
            }

        error_info = APIErrorDetector.get_error_info(message, status_code=status_code)
        normalized_error_type = self._normalize_error_type(error_info["error_type"])
        return {
            "error_type": normalized_error_type,
            "message": message,
            "status_code": status_code,
        }

    def _extract_runtime_error_type(self, exc: Exception) -> Optional[str]:
        if getattr(exc, "is_rate_limit", False):
            return "rate_limit"

        runtime_error_type = getattr(exc, "error_type", None)
        if not runtime_error_type:
            return None

        return {
            "authentication": "auth_error",
            "auth_error": "auth_error",
            "rate_limit": "rate_limit",
            "timeout": "network_error",
            "network_error": "network_error",
            "server_error": "server_error",
            "model_unavailable": "model_unavailable",
            "billing_error": "billing_error",
            "invalid_request": "invalid_request",
            "invalid_dimensions": "invalid_dimensions",
            "invalid_response": "invalid_response",
            "unknown": "unknown_error",
        }.get(runtime_error_type, runtime_error_type)

    def _extract_status_code(self, exc: Exception, message: str) -> Optional[int]:
        raw_status_code = getattr(exc, "status_code", None)
        if isinstance(raw_status_code, int):
            return raw_status_code

        match = _STATUS_CODE_RE.search(message)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _classify_status_code(self, status_code: Optional[int]) -> Optional[str]:
        if status_code is None:
            return None
        if status_code == 402:
            return "billing_error"
        if status_code == 404:
            return "model_unavailable"
        if status_code == 429:
            return "rate_limit"
        if status_code in {401, 403}:
            return "auth_error"
        if status_code in {400, 422}:
            return "invalid_request"
        if status_code in {500, 502, 503, 504}:
            return "server_error"
        return None

    def _normalize_error_type(self, error_type: str) -> str:
        if error_type == ErrorType.INSUFFICIENT_PERMISSIONS.value:
            return "auth_error"
        if error_type == ErrorType.PAYMENT_REQUIRED.value:
            return "billing_error"
        return error_type

    def _get_auth_manager(self) -> VertexAIAuthManager:
        if self._auth_manager is None:
            self._auth_manager = self._auth_manager_factory()
        return self._auth_manager

    def _get_llm_client(self) -> VertexLLMClient:
        if self._llm_client is None:
            self._llm_client = self._llm_client_factory()
        return self._llm_client

    def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = self._embedding_service_factory()
        return self._embedding_service


_probe_service_instance: Optional[HealthProbeService] = None


def get_health_probe_service() -> HealthProbeService:
    """Return the singleton cached health probe service."""
    global _probe_service_instance
    if _probe_service_instance is None:
        _probe_service_instance = HealthProbeService()
    return _probe_service_instance


__all__ = [
    "HealthProbeService",
    "get_health_probe_service",
]
