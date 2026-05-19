"""Endpoint skeleton for the explicit-only Agent Context API."""

import asyncio
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .dependencies import verify_agent_context_token
from .models import (
    AgentContextArtifactReceipt,
    AgentContextRequest,
    AgentContextResponse,
    AgentSourceExpandRequest,
    AgentSourceExpandResponse,
    SelectionUsed,
)
from .. import config
from ..models.expert import Expert
from ..models.base import SessionLocal
from ..services.agent_context_service import (
    AgentContextInvalidSourceKey,
    AgentContextSearchUnavailable,
    AgentContextService,
    SUPPORTED_AGENT_CONTEXT_RESPONSE_MODES,
)
from ..services.artifact_retention_service import agent_context_results_dir


AGENT_CONTEXT_EXPERT_GROUPS = {
    "tech": [
        "ai_architect",
        "neuraldeep",
        "ilia_izmailov",
        "polyakov",
        "etechlead",
        "glebkudr",
        "ostrikov",
        "pashazloy",
    ],
    "tech_business": [
        "ai_grabli",
        "refat",
        "akimov",
        "llm_under_hood",
        "elkornacio",
        "doronin",
        "air_ai",
        "silicbag",
        "kornish",
    ],
}

_KNOWN_AGENT_CONTEXT_EXPERT_IDS = {
    expert_id
    for group_expert_ids in AGENT_CONTEXT_EXPERT_GROUPS.values()
    for expert_id in group_expert_ids
} | {"video_hub"}
_AGENT_CONTEXT_EXCLUDED_EXPERT_IDS = {"video_hub"}

_SUPPORTED_EXPERT_SCOPES = {"all", "group", "custom", "none"}
_REQUEST_ID_RE = re.compile(r"^[a-f0-9-]{36}$")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent-context"])


def _agent_context_results_dir() -> Path:
    """Return the durable Agent Context result directory."""

    return agent_context_results_dir()


def _agent_context_result_path(request_id: str) -> Path:
    """Build a safe path for a saved Agent Context response."""

    if not _REQUEST_ID_RE.match(request_id):
        raise HTTPException(status_code=400, detail="Invalid request_id")
    return _agent_context_results_dir() / f"{request_id}.json"


def _response_payload(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        payload = response.model_dump(mode="json")
    else:
        payload = response
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent Context response is not a JSON object",
        )
    return payload


def _persist_agent_context_result(response: Any) -> tuple[Path, int]:
    """Persist a completed Agent Context response before returning a compact receipt."""

    payload = _response_payload(response)
    request_id = str(payload.get("request_id") or "")
    result_path = _agent_context_result_path(request_id)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    tmp_path = result_path.with_suffix(".json.tmp")
    tmp_path.write_bytes(serialized)
    os.replace(tmp_path, result_path)

    logger.info(
        "Saved Agent Context result artifact: request_id=%s bytes=%s path=%s",
        request_id,
        len(serialized),
        result_path,
    )
    return result_path, len(serialized)


def _agent_context_result_url(request_id: str) -> str:
    return f"/api/v1/agent/context/{request_id}/result"


def _artifact_receipt(
    *,
    response: Any,
    operation: str,
    response_bytes: int,
) -> AgentContextArtifactReceipt:
    payload = _response_payload(response)
    experts = payload.get("experts") or []
    sources = payload.get("sources") or []
    return AgentContextArtifactReceipt(
        operation=operation,
        request_id=str(payload["request_id"]),
        mode=str(payload.get("mode") or "unknown"),
        result_url=_agent_context_result_url(str(payload["request_id"])),
        response_bytes=response_bytes,
        query=payload.get("query"),
        expert_count=len(experts) if isinstance(experts, list) else 0,
        source_keys=[
            str(source.get("source_key"))
            for source in sources
            if isinstance(source, dict) and source.get("source_key")
        ],
        warnings=list(payload.get("warnings") or []),
    )


def get_db():
    """Database dependency for Agent Context API requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_expert_ids(expert_ids: Iterable[str] | None) -> list[str]:
    """Normalize explicit expert IDs while preserving caller order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_expert_id in expert_ids or []:
        expert_id = raw_expert_id.strip()
        if not expert_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expert_filter must not contain empty expert IDs",
            )
        if expert_id not in seen:
            normalized.append(expert_id)
            seen.add(expert_id)
    return normalized


def _load_agent_context_expert_ids(
    db: Session,
    *,
    include_excluded: bool = False,
) -> list[str]:
    query = db.query(Expert.expert_id).order_by(Expert.expert_id)
    expert_ids = [row[0] for row in query.all()]
    if include_excluded:
        return expert_ids
    return [
        expert_id
        for expert_id in expert_ids
        if expert_id not in _AGENT_CONTEXT_EXCLUDED_EXPERT_IDS
    ]


def _known_agent_context_expert_ids(db: Session) -> set[str]:
    return (
        set(_load_agent_context_expert_ids(db, include_excluded=True))
        | _KNOWN_AGENT_CONTEXT_EXPERT_IDS
    )


def _build_selection_used(agent_request: AgentContextRequest, db: Session) -> SelectionUsed:
    """Validate MVP request options and return normalized selection metadata."""
    if agent_request.response_mode not in SUPPORTED_AGENT_CONTEXT_RESPONSE_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Agent Context API supports response_mode values: "
                f"{', '.join(sorted(SUPPORTED_AGENT_CONTEXT_RESPONSE_MODES))}"
            ),
        )

    if agent_request.include_drift_comment_groups:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="include_drift_comment_groups is not implemented for the MVP",
        )

    if agent_request.synthesis_level != "none":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="synthesis_level other than 'none' is not implemented for the MVP",
        )

    expert_scope = agent_request.expert_scope
    if expert_scope not in _SUPPORTED_EXPERT_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expert_scope must be one of: all, group, custom, none",
        )

    expert_group = agent_request.expert_group
    expert_filter = _normalize_expert_ids(agent_request.expert_filter)

    if expert_scope == "group":
        if expert_group not in AGENT_CONTEXT_EXPERT_GROUPS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expert_scope='group' requires a known expert_group",
            )
        expert_filter = list(AGENT_CONTEXT_EXPERT_GROUPS[expert_group])
    elif expert_scope == "custom":
        expert_group = None
        if not expert_filter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expert_scope='custom' requires a non-empty expert_filter",
            )
        unknown_expert_ids = [
            expert_id
            for expert_id in expert_filter
            if expert_id not in _known_agent_context_expert_ids(db)
        ]
        if unknown_expert_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Unknown expert IDs",
                    "unknown_expert_ids": unknown_expert_ids,
                },
            )
    elif expert_scope == "all":
        expert_group = None
        expert_filter = None
    else:
        expert_group = None
        expert_filter = None
        if not agent_request.include_reddit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="expert_scope='none' requires include_reddit=true",
            )

    if agent_request.include_reddit:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="include_reddit is not implemented for the Agent Context API MVP",
        )

    return SelectionUsed(
        expert_scope=expert_scope,
        expert_group=expert_group,
        expert_filter=expert_filter,
        include_reddit=agent_request.include_reddit,
        include_main_source_comments=agent_request.include_main_source_comments,
        include_drift_comment_groups=agent_request.include_drift_comment_groups,
        synthesis_level=agent_request.synthesis_level,
        use_recent_only=agent_request.use_recent_only,
        use_super_passport=True,
    )


def _resolve_expert_ids(selection_used: SelectionUsed, db: Session) -> list[str]:
    if selection_used.expert_scope == "all":
        return _load_agent_context_expert_ids(db)

    return list(selection_used.expert_filter or [])


def _reject_unsupported_video_hub(expert_ids: list[str]) -> None:
    if "video_hub" in expert_ids:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="video_hub source_bundle is not implemented for the Agent Context API",
        )


def _enforce_response_size(response: Any) -> None:
    """Fail closed if a response exceeds the configured transport cap."""
    max_bytes = config.AGENT_CONTEXT_MAX_RESPONSE_BYTES
    if max_bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AGENT_CONTEXT_MAX_RESPONSE_BYTES must be positive",
        )

    response_bytes = len(response.model_dump_json().encode("utf-8"))
    if response_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Agent Context API response exceeds configured max bytes",
        )


async def _build_agent_context_response(
    agent_request: AgentContextRequest,
    http_request: Request,
    db: Session,
    start_time: float,
) -> AgentContextResponse:
    selection_used = _build_selection_used(agent_request, db)
    expert_ids = _resolve_expert_ids(selection_used, db)
    _reject_unsupported_video_hub(expert_ids)
    request_id = getattr(http_request.state, "request_id", "unknown")

    service = AgentContextService(db)
    try:
        response = await service.build_response(
            agent_request=agent_request,
            selection_used=selection_used,
            expert_ids=expert_ids,
            request_id=request_id,
            start_time=start_time,
        )
    except AgentContextSearchUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    _enforce_response_size(response)
    return response


async def _build_source_expand_response(
    expand_request: AgentSourceExpandRequest,
    http_request: Request,
    db: Session,
    start_time: float,
) -> AgentSourceExpandResponse:
    request_id = getattr(http_request.state, "request_id", "unknown")
    service = AgentContextService(db)
    try:
        response = await service.build_expand_response(
            expand_request=expand_request,
            request_id=request_id,
            start_time=start_time,
        )
    except AgentContextInvalidSourceKey as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    _enforce_response_size(response)
    return response


@router.get(
    "/context/{request_id}/result",
    dependencies=[Depends(verify_agent_context_token)],
)
async def get_saved_agent_context_result(request_id: str):
    """Fetch a saved Agent Context response by request_id."""

    result_path = _agent_context_result_path(request_id)
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Agent Context result not found")

    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error(
            "Saved Agent Context result is invalid JSON: %s",
            result_path,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Saved Agent Context result is invalid",
        ) from exc

    return JSONResponse(content=payload)


@router.post(
    "/context",
    response_model=AgentContextResponse,
    dependencies=[Depends(verify_agent_context_token)],
)
async def create_agent_context(
    agent_request: AgentContextRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AgentContextResponse:
    """Return the authenticated Agent Context API skeleton response."""
    start_time = time.perf_counter()
    timeout_seconds = config.AGENT_CONTEXT_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AGENT_CONTEXT_TIMEOUT_SECONDS must be positive",
        )

    try:
        return await asyncio.wait_for(
            _build_agent_context_response(agent_request, http_request, db, start_time),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Agent Context API request exceeded configured timeout",
        ) from exc


@router.post(
    "/context/artifact",
    response_model=AgentContextArtifactReceipt,
    dependencies=[Depends(verify_agent_context_token)],
)
async def create_agent_context_artifact(
    agent_request: AgentContextRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AgentContextArtifactReceipt:
    """Build, save, and return a compact receipt for an Agent Context response."""
    start_time = time.perf_counter()
    timeout_seconds = config.AGENT_CONTEXT_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AGENT_CONTEXT_TIMEOUT_SECONDS must be positive",
        )

    try:
        response = await asyncio.wait_for(
            _build_agent_context_response(agent_request, http_request, db, start_time),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Agent Context API request exceeded configured timeout",
        ) from exc

    _, response_bytes = _persist_agent_context_result(response)
    return _artifact_receipt(
        response=response,
        operation="ask",
        response_bytes=response_bytes,
    )


@router.post(
    "/context/expand",
    response_model=AgentSourceExpandResponse,
    dependencies=[Depends(verify_agent_context_token)],
)
async def expand_agent_context_sources(
    expand_request: AgentSourceExpandRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AgentSourceExpandResponse:
    """Return exact raw/capped Agent Context sources by source_key."""
    start_time = time.perf_counter()
    timeout_seconds = config.AGENT_CONTEXT_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AGENT_CONTEXT_TIMEOUT_SECONDS must be positive",
        )

    try:
        return await asyncio.wait_for(
            _build_source_expand_response(
                expand_request,
                http_request,
                db,
                start_time,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Agent Context API source expansion exceeded configured timeout",
        ) from exc


@router.post(
    "/context/expand/artifact",
    response_model=AgentContextArtifactReceipt,
    dependencies=[Depends(verify_agent_context_token)],
)
async def expand_agent_context_sources_artifact(
    expand_request: AgentSourceExpandRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AgentContextArtifactReceipt:
    """Build, save, and return a compact receipt for an exact source expansion."""
    start_time = time.perf_counter()
    timeout_seconds = config.AGENT_CONTEXT_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AGENT_CONTEXT_TIMEOUT_SECONDS must be positive",
        )

    try:
        response = await asyncio.wait_for(
            _build_source_expand_response(
                expand_request,
                http_request,
                db,
                start_time,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Agent Context API source expansion exceeded configured timeout",
        ) from exc

    _, response_bytes = _persist_agent_context_result(response)
    return _artifact_receipt(
        response=response,
        operation="expand",
        response_bytes=response_bytes,
    )
