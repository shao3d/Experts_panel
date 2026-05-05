"""Endpoint skeleton for the explicit-only Agent Context API."""

import asyncio
import time
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .dependencies import verify_agent_context_token
from .models import AgentContextRequest, AgentContextResponse, SelectionUsed
from .. import config
from ..models.base import SessionLocal
from ..services.agent_context_service import (
    AgentContextSearchUnavailable,
    AgentContextService,
)


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

_SUPPORTED_EXPERT_SCOPES = {"all", "group", "custom", "none"}

router = APIRouter(prefix="/api/v1/agent", tags=["agent-context"])


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


def _build_selection_used(agent_request: AgentContextRequest) -> SelectionUsed:
    """Validate MVP request options and return normalized selection metadata."""
    if agent_request.response_mode != "source_bundle":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent Context API MVP supports only response_mode='source_bundle'",
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
            if expert_id not in _KNOWN_AGENT_CONTEXT_EXPERT_IDS
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


def _resolve_expert_ids(selection_used: SelectionUsed) -> list[str]:
    if selection_used.expert_scope == "all":
        expert_ids: list[str] = []
        for group_expert_ids in AGENT_CONTEXT_EXPERT_GROUPS.values():
            expert_ids.extend(group_expert_ids)
        return _normalize_expert_ids(expert_ids)

    return list(selection_used.expert_filter or [])


def _reject_unsupported_video_hub(expert_ids: list[str]) -> None:
    if "video_hub" in expert_ids:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="video_hub source_bundle is not implemented for the Agent Context API MVP",
        )


def _enforce_response_size(response: AgentContextResponse) -> None:
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
    selection_used = _build_selection_used(agent_request)
    expert_ids = _resolve_expert_ids(selection_used)
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
