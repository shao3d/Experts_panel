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
import json
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
# Probe as a structured JSON acknowledgment so Gemini 2.5 and Gemini 3
# families both answer with the same verifiable envelope. The earlier
# text-only "Response with OK only." probe made Gemini 3 models emit
# verbose acknowledgements ("Sure, OK." / "I'm here and ready.") which
# failed the `startswith("OK")` check and falsely marked those models
# as `unavailable`.
_PROBE_JSON_PROMPT = (
    "Return a single JSON object with a 'status' field set to 'ok'. "
    'Example: {"status": "ok"}. No other text, no markdown fences.'
)
_PROBE_OK_STATUS = "ok"

# Fallback regex: tolerate JSON wrapped in a chatty preamble or in
# markdown fences. Captures a top-level {...} block that contains a
# `"status": "ok"` pair anywhere (case-insensitive). Nested status is
# ignored on purpose -- the top-level field is the contract.
_PROBE_OK_PATTERN = re.compile(
    r'\{[^{}]*"status"\s*:\s*"ok"[^{}]*\}',
    re.IGNORECASE,
)


def _classify_probe_response(content: str) -> Tuple[bool, str]:
    """Classify a probe response envelope.

    Returns ``(ok, error_type)`` where ``error_type`` is one of:
      - ``""`` (empty) when ``ok`` is True,
      - ``"empty_response"`` when the response is empty / whitespace-only
        (Vertex can return this for several reasons -- ``finish_reason``
        in {SAFETY, OTHER, MAX_TOKENS} with empty body, quota exhaustion,
        internal 5xx with no body -- the model is *not* necessarily
        unreachable, it just didn't return a parseable body for this
        particular probe prompt; ops should investigate the underlying
        finish_reason via the Vertex response metadata, not assume
        "safety policy"),
      - ``"malformed_json"`` when no parseable JSON envelope can be
        located in the response,
      - ``"invalid_response"`` when a JSON envelope parsed cleanly but
        ``status`` is missing or disagrees with "ok".

    The function deliberately inspects the **top-level** ``status`` only
    -- nested ``status`` fields are intentionally ignored to keep the
    contract stable across model families.
    """
    text = (content or "").strip()
    if not text:
        # Empty / whitespace-only. Distinguish from genuinely garbage
        # responses so ops can spot quota/SAFETY/OTHER causes vs. plain
        # prompt-misformat.
        return False, "empty_response"

    # Preferred path: pure JSON envelope, exactly the shape the prompt
    # asks for.
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            status = str(payload.get("status", "")).strip().lower()
            if status == _PROBE_OK_STATUS:
                return True, ""
            return False, "invalid_response"
    except (ValueError, TypeError):
        pass

    # Fallback: JSON wrapped in chatter ("Sure here is the JSON: {...}")
    # or in markdown fences (```json\n{...}\n```). The regex only matches
    # a single top-level {...} block, so nested objects cannot trick it.
    if _PROBE_OK_PATTERN.search(text):
        return True, ""

    return False, "malformed_json"
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
                messages=[{"role": "user", "content": _PROBE_JSON_PROMPT}],
                temperature=0,
                max_tokens=32,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            ok, error_type = _classify_probe_response(content)
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
                result["error_type"] = error_type
                result["message"] = f"Unexpected probe response: {content[:120]}"
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


async def log_critical_models_availability(
    logger: logging.Logger,
    *,
    timeout_seconds: float = 15.0,
) -> Dict[str, str]:
    """Probe tracked Gemini models and log a WARNING for any that are unavailable.

    Designed for the FastAPI lifespan startup hook. Mirrors the active
    readiness contract used by ``/health`` and ``/health/live`` so a broken
    ``MODEL_*`` config is surfaced immediately at boot rather than the
    first time a user runs a query many minutes later.

    Fail-open: never raises. ``timeout_seconds`` bounds the whole probe so a
    slow or cold-starting Vertex AI cannot stall FastAPI lifespan startup; on
    timeout the helper logs a WARNING and returns ``{}``.
    Returns ``{model_name: status}`` for tests and callers that want to
    programmatically inspect the result.
    """
    auth_manager = get_vertex_ai_auth_manager()
    if not auth_manager.is_configured():
        logger.info(
            "Vertex AI auth not configured at startup -- skipping critical-model "
            "availability check"
        )
        return {}

    try:
        service = get_health_probe_service()
        summary = await asyncio.wait_for(
            service.warm_cache(), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Critical-model availability probe timed out after %.1fs at startup; "
            "skipping liveness check (probe will retry via /health later).",
            timeout_seconds,
        )
        return {}
    except Exception as exc:  # defensive: never let probe failure halt startup
        logger.warning(
            "Critical-model availability probe failed at startup: %s", exc
        )
        return {}

    availability = summary.get("model_availability") or {}
    result: Dict[str, str] = {}
    for model, info in availability.items():
        if not isinstance(info, dict):
            continue
        status = str(info.get("status") or "unknown")
        result[model] = status
        if status == "unavailable":
            status_code = info.get("status_code")
            code_hint = f" (status_code={status_code})" if status_code else ""
            raw_message = str(info.get("message") or "").splitlines()[0]
            message = raw_message[:240] or "no detail"
            logger.warning(
                "Vertex AI model unavailable at startup: %s%s -- %s. Queries "
                "that reach this model will degrade until you either rename "
                "the matching MODEL_* env var to a model exposed in your "
                "Vertex AI model garden (https://console.cloud.google.com/"
                "vertex-ai/model-garden) or unset the env var to inherit the "
                "running default in backend/src/config.py.",
                model, code_hint, message,
            )
        elif status == "unknown" and info.get("error_type"):
            logger.info(
                "Vertex AI model probe inconclusive at startup: %s "
                "(error_type=%s)",
                model,
                info.get("error_type"),
            )
        # status == "available" is the happy path -- no log spam at INFO.

    # Defensive: if Vertex auth was configured but the probe produced an empty
    # summary for any reason, surface the gap instead of silently "all good".
    if not result:
        logger.warning(
            "Critical-model availability probe returned no entries at startup; "
            "check that MODEL_MAP and Vertex AI auth are configured."
        )
    return result


__all__ = [
    "HealthProbeService",
    "get_health_probe_service",
    "log_critical_models_availability",
]
