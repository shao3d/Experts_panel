import json
import uuid

import pytest
from fastapi import HTTPException

from src.api import simplified_query_endpoint as endpoint
from src.api.models import (
    ConfidenceLevel,
    ExpertResponse,
    MultiExpertQueryResponse,
    QueryRequest,
)


def _sample_response(request_id: str) -> MultiExpertQueryResponse:
    return MultiExpertQueryResponse(
        query="How do experts use Codex for UI design?",
        expert_responses=[
            ExpertResponse(
                expert_id="refat",
                expert_name="Refat",
                channel_username="nobilix",
                answer="Use agent workflows with source-backed checks.",
                main_sources=[],
                confidence=ConfidenceLevel.HIGH,
                posts_analyzed=3,
                processing_time_ms=1234,
            )
        ],
        reddit_response=None,
        meta_synthesis="Cross-expert synthesis",
        total_processing_time_ms=5678,
        request_id=request_id,
    )


def test_query_result_artifact_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("QUERY_RESULTS_DIR", str(tmp_path))
    request_id = str(uuid.uuid4())

    result_path = endpoint._persist_query_result(_sample_response(request_id))

    assert result_path == tmp_path / f"{request_id}.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["request_id"] == request_id
    assert payload["expert_responses"][0]["expert_id"] == "refat"
    assert payload["meta_synthesis"] == "Cross-expert synthesis"


def test_saved_query_result_route_is_registered():
    routes = {
        getattr(route, "path", None): getattr(route, "methods", set())
        for route in endpoint.router.routes
    }

    assert "/api/v1/query/{request_id}/result" in routes
    assert "GET" in routes["/api/v1/query/{request_id}/result"]


@pytest.mark.asyncio
async def test_sse_progress_events_carry_request_id():
    request_id = str(uuid.uuid4())
    request = QueryRequest(
        query="Smoke request id propagation",
        expert_filter=[],
        include_reddit=False,
        stream_progress=True,
    )

    events = []
    async for raw_event in endpoint.event_generator_parallel(request, db=None, request_id=request_id):
        payload = raw_event.removeprefix("data: ").strip()
        events.append(json.loads(payload))

    assert events[0]["event_type"] == "start"
    assert events[0]["data"]["request_id"] == request_id
    assert events[1]["event_type"] == "error"
    assert events[1]["data"]["request_id"] == request_id


@pytest.mark.parametrize("bad_request_id", ["../secret", "not-a-uuid", "abc.json"])
def test_query_result_path_rejects_unsafe_request_ids(tmp_path, monkeypatch, bad_request_id):
    monkeypatch.setenv("QUERY_RESULTS_DIR", str(tmp_path))

    with pytest.raises(HTTPException) as exc:
        endpoint._query_result_path(bad_request_id)

    assert exc.value.status_code == 400
