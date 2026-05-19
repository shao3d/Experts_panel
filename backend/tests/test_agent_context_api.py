#!/usr/bin/env python3
"""Targeted tests for the Agent Context API MVP skeleton."""

import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.api import dependencies
from src.api.agent_context_endpoint import AGENT_CONTEXT_EXPERT_GROUPS
from src.api.main import app
from src.services import health_probe_service as health_probe_module
from src.api.models import (
    AgentDigestComments,
    AgentDigestOmittedCounts,
    AgentDigestSourceRef,
    AgentExpertSourceBundle,
    AgentExternalLink,
    AgentLinkedContext,
    AgentMainSource,
    AgentSourceComment,
    AgentSourceComments,
)
from src.models.base import SessionLocal
from src.models.expert import Expert
from src.services.agent_context_service import (
    AgentContextSearchContext,
    AgentContextService,
    AgentExpertDigestReducer,
)
from src.services import agent_context_service as agent_context_module

_ORIGINAL_PREPARE_SEARCH_CONTEXT = AgentContextService._prepare_search_context
_ORIGINAL_LOAD_CANDIDATE_POSTS_WITH_EMBEDDINGS = (
    AgentContextService._load_candidate_posts_with_embeddings
)


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
    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts",
        lambda self, expert_id, cutoff_date=None: [],
    )
    monkeypatch.setattr(
        AgentContextService,
        "_get_expert_metadata",
        lambda self, expert_id: {
            "expert_name": expert_id,
            "channel_username": expert_id,
        },
    )

    async def fake_prepare_search_context(self, query):
        return AgentContextSearchContext(
            scout_query="ai OR agents OR sales",
            query_embedding=[0.1] * 768,
            warnings=[],
        )

    async def fake_load_candidate_posts_with_embeddings(
        self,
        *,
        expert_id,
        query,
        cutoff_date,
        search_context,
        warnings,
    ):
        return self._load_candidate_posts(expert_id, cutoff_date)

    monkeypatch.setattr(
        AgentContextService,
        "_prepare_search_context",
        fake_prepare_search_context,
    )
    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts_with_embeddings",
        fake_load_candidate_posts_with_embeddings,
    )
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


def _db_expert_ids(*, include_video_hub: bool = False) -> list[str]:
    db = SessionLocal()
    try:
        expert_ids = [
            row[0]
            for row in db.query(Expert.expert_id).order_by(Expert.expert_id).all()
        ]
    finally:
        db.close()
    if include_video_hub:
        return expert_ids
    return [expert_id for expert_id in expert_ids if expert_id != "video_hub"]


def _fake_post(telegram_message_id: int, created_at: str):
    return SimpleNamespace(
        telegram_message_id=telegram_message_id,
        message_text=f"Post {telegram_message_id} content long enough for retrieval",
        author_name="Refat",
        created_at=datetime.fromisoformat(created_at),
    )


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


def test_agent_context_valid_token_returns_source_bundle_shape():
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
    assert [expert["expert_id"] for expert in payload["experts"]] == [
        "refat",
        "akimov",
    ]
    assert payload["experts"][0]["main_sources"] == []
    assert payload["experts"][0]["no_results_reason"] == "no_runtime_posts"
    assert payload["selection_used"] == {
        "expert_scope": "custom",
        "expert_group": None,
        "expert_filter": ["refat", "akimov"],
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": False,
        "use_super_passport": True,
    }
    assert "source_selection" in payload["pipeline_used"]
    assert "reduce_answer_synthesis" in payload["pipeline_skipped"]
    assert "agent_context_source_pipeline_not_implemented" not in payload["warnings"]


def test_agent_context_artifact_endpoint_saves_result_for_later_fetch(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        config,
        "AGENT_CONTEXT_RESULTS_DIR",
        str(tmp_path / "agent-context-results"),
    )

    with TestClient(app) as client:
        receipt_response = client.post(
            "/api/v1/agent/context/artifact",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_filter=["refat"]),
        )

        assert receipt_response.status_code == 200, receipt_response.text
        receipt = receipt_response.json()
        assert receipt["kind"] == "agent_context_artifact"
        assert receipt["operation"] == "ask"
        assert receipt["mode"] == "source_bundle"
        assert receipt["expert_count"] == 1
        assert receipt["response_bytes"] > 0
        assert receipt["result_url"] == (
            f"/api/v1/agent/context/{receipt['request_id']}/result"
        )

        unauthenticated = client.get(receipt["result_url"])
        assert unauthenticated.status_code == 403

        result_response = client.get(
            receipt["result_url"],
            headers=_auth_headers(),
        )

    assert result_response.status_code == 200, result_response.text
    payload = result_response.json()
    assert payload["request_id"] == receipt["request_id"]
    assert payload["mode"] == "source_bundle"
    assert [expert["expert_id"] for expert in payload["experts"]] == ["refat"]


def test_agent_context_forces_embedding_hybrid_search_even_if_client_disables_toggle(
    monkeypatch,
):
    observed = {
        "scout_queries": [],
        "embedding_queries": [],
        "hybrid_calls": [],
        "standard_fallback_calls": [],
    }

    async def real_prepare_search_context(self, query):
        return await _ORIGINAL_PREPARE_SEARCH_CONTEXT(self, query)

    async def real_load_candidate_posts_with_embeddings(
        self,
        *,
        expert_id,
        query,
        cutoff_date,
        search_context,
        warnings,
    ):
        return await _ORIGINAL_LOAD_CANDIDATE_POSTS_WITH_EMBEDDINGS(
            self,
            expert_id=expert_id,
            query=query,
            cutoff_date=cutoff_date,
            search_context=search_context,
            warnings=warnings,
        )

    monkeypatch.setattr(
        AgentContextService,
        "_prepare_search_context",
        real_prepare_search_context,
    )
    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts_with_embeddings",
        real_load_candidate_posts_with_embeddings,
    )
    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts",
        lambda self, expert_id, cutoff_date=None: observed["standard_fallback_calls"].append(
            expert_id
        )
        or [],
    )

    class FakeScoutService:
        async def generate_match_query(self, query):
            observed["scout_queries"].append(query)
            return "ai OR agents OR sales", True

    class FakeEmbeddingService:
        async def embed_query(self, query):
            observed["embedding_queries"].append(query)
            return [0.25] * 768

    class FakeHybridRetrievalService:
        def __init__(self, db):
            self.db = db

        async def search_posts(
            self,
            *,
            expert_id,
            query,
            match_query,
            cutoff_date,
            query_embedding,
        ):
            observed["hybrid_calls"].append(
                {
                    "expert_id": expert_id,
                    "query": query,
                    "match_query": match_query,
                    "cutoff_date": cutoff_date,
                    "query_embedding": query_embedding,
                }
            )
            return [], {
                "mode": "hybrid",
                "vector_count": 0,
                "fts5_count": 0,
                "merged_count": 0,
                "final_count": 0,
            }

    monkeypatch.setattr(agent_context_module, "AIScoutService", FakeScoutService)
    monkeypatch.setattr(
        agent_context_module,
        "get_embedding_service",
        lambda: FakeEmbeddingService(),
    )
    monkeypatch.setattr(
        agent_context_module,
        "HybridRetrievalService",
        FakeHybridRetrievalService,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(
                expert_filter=["refat", "akimov"],
                use_super_passport=False,
            ),
        )

    assert response.status_code == 200, response.text
    assert response.json()["selection_used"]["use_super_passport"] is True
    assert "query_embedding" in response.json()["pipeline_used"]
    assert "hybrid_retrieval" in response.json()["pipeline_used"]
    assert observed["scout_queries"] == [_agent_context_payload()["query"]]
    assert observed["embedding_queries"] == [_agent_context_payload()["query"]]
    assert observed["standard_fallback_calls"] == []
    assert [call["expert_id"] for call in observed["hybrid_calls"]] == [
        "refat",
        "akimov",
    ]
    assert all(
        call["query_embedding"] == [0.25] * 768
        for call in observed["hybrid_calls"]
    )


def test_agent_context_fails_closed_when_query_embedding_is_unavailable(
    monkeypatch,
):
    observed = {"standard_fallback_calls": []}

    async def real_prepare_search_context(self, query):
        return await _ORIGINAL_PREPARE_SEARCH_CONTEXT(self, query)

    monkeypatch.setattr(
        AgentContextService,
        "_prepare_search_context",
        real_prepare_search_context,
    )
    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts",
        lambda self, expert_id, cutoff_date=None: observed["standard_fallback_calls"].append(
            expert_id
        )
        or [],
    )

    class FakeScoutService:
        async def generate_match_query(self, query):
            return "ai OR agents OR sales", True

    class FailingEmbeddingService:
        async def embed_query(self, query):
            raise RuntimeError("embedding backend unavailable")

    monkeypatch.setattr(agent_context_module, "AIScoutService", FakeScoutService)
    monkeypatch.setattr(
        agent_context_module,
        "get_embedding_service",
        lambda: FailingEmbeddingService(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_filter=["refat"]),
        )

    assert response.status_code == 503, response.text
    assert response.json()["message"] == "agent_context_embedding_search_unavailable"
    assert observed["standard_fallback_calls"] == []


def test_agent_context_group_tech_resolves_expected_roster():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(
                expert_scope="group",
                expert_group="tech",
                expert_filter=None,
            ),
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [expert["expert_id"] for expert in payload["experts"]] == AGENT_CONTEXT_EXPERT_GROUPS["tech"]
    assert payload["selection_used"]["expert_filter"] == AGENT_CONTEXT_EXPERT_GROUPS["tech"]


def test_agent_context_all_excludes_video_hub():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_scope="all", expert_filter=["video_hub"]),
        )

    assert response.status_code == 200, response.text
    expert_ids = [expert["expert_id"] for expert in response.json()["experts"]]
    assert "video_hub" not in expert_ids
    assert expert_ids == _db_expert_ids()
    assert response.json()["selection_used"]["expert_filter"] is None


def test_agent_context_custom_accepts_database_expert_outside_static_groups():
    static_group_ids = {
        expert_id
        for group_expert_ids in AGENT_CONTEXT_EXPERT_GROUPS.values()
        for expert_id in group_expert_ids
    }
    candidates = [
        expert_id
        for expert_id in _db_expert_ids()
        if expert_id not in static_group_ids
    ]
    assert candidates, "test database should include at least one DB-only expert"

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(
                expert_scope="custom",
                expert_filter=[candidates[0]],
            ),
        )

    assert response.status_code == 200, response.text
    assert [expert["expert_id"] for expert in response.json()["experts"]] == [
        candidates[0]
    ]


def test_agent_context_processes_experts_with_bounded_parallelism(monkeypatch):
    monkeypatch.setattr(config, "MAX_CONCURRENT_EXPERTS", 2)
    active_count = 0
    max_active_count = 0
    started_expert_ids = []

    async def fake_build_expert_bundle(
        self,
        *,
        expert_id,
        agent_request,
        search_context,
        warnings,
    ):
        nonlocal active_count, max_active_count
        started_expert_ids.append(expert_id)
        active_count += 1
        max_active_count = max(max_active_count, active_count)
        await asyncio.sleep(0.01)
        active_count -= 1
        return self._empty_expert_bundle(
            expert_id=expert_id,
            no_results_reason="parallel_test",
        )

    monkeypatch.setattr(
        AgentContextService,
        "_build_expert_bundle",
        fake_build_expert_bundle,
    )

    expert_filter = ["refat", "akimov", "ai_grabli", "llm_under_hood"]
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_filter=expert_filter),
        )

    assert response.status_code == 200, response.text
    assert [expert["expert_id"] for expert in response.json()["experts"]] == expert_filter
    assert max_active_count == 2
    assert set(started_expert_ids) == set(expert_filter)


def test_agent_context_unknown_expert_returns_400():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_filter=["unknown_expert"]),
        )

    assert response.status_code == 400, response.text
    assert response.json()["message"]["unknown_expert_ids"] == ["unknown_expert"]


def test_agent_context_video_hub_returns_501():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_filter=["video_hub"]),
        )

    assert response.status_code == 501, response.text
    assert "video_hub source_bundle" in response.json()["message"]


def test_agent_context_rejects_unimplemented_deep_modes():
    with TestClient(app) as client:
        drift_response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(include_drift_comment_groups=True),
        )
        synthesis_response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(synthesis_level="compact"),
        )
        reddit_response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(include_reddit=True),
        )

    assert drift_response.status_code == 501, drift_response.text
    assert synthesis_response.status_code == 501, synthesis_response.text
    assert reddit_response.status_code == 501, reddit_response.text


def test_agent_context_builds_sources_context_and_comments(monkeypatch):
    posts = [
        _fake_post(101, "2026-04-10T12:00:00"),
        _fake_post(102, "2026-04-09T12:00:00"),
        _fake_post(103, "2026-04-08T12:00:00"),
    ]

    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts",
        lambda self, expert_id, cutoff_date=None: posts,
    )

    class FakeMapService:
        def __init__(self, **kwargs):
            pass

        async def process(self, **kwargs):
            return {
                "relevant_posts": [
                    {
                        "telegram_message_id": 101,
                        "relevance": "HIGH",
                        "reason": "Direct match",
                    },
                    {
                        "telegram_message_id": 102,
                        "relevance": "MEDIUM",
                        "reason": "Useful secondary source",
                    },
                    {
                        "telegram_message_id": 103,
                        "relevance": "LOW",
                        "reason": "Too broad",
                    },
                ]
            }

    class FakeMediumScoringService:
        def __init__(self, **kwargs):
            pass

        async def score_medium_posts(self, medium_posts, **kwargs):
            return [
                {
                    **medium_posts[0],
                    "score": 0.91,
                    "score_reason": "Complements the high source",
                }
            ]

    class FakeResolveService:
        async def process(self, **kwargs):
            return {
                "enriched_posts": [
                    {
                        "telegram_message_id": 101,
                        "relevance": "HIGH",
                        "reason": "Direct match",
                        "content": (
                            "High content references "
                            "[LangGraph](https://github.com/langchain-ai/langgraph) "
                            "and https://example.com/ai-agents-report."
                        ),
                        "author": "Refat",
                        "created_at": "2026-04-10T12:00:00",
                        "is_original": True,
                    },
                    {
                        "telegram_message_id": 201,
                        "relevance": "CONTEXT",
                        "reason": "Linked context",
                        "content": "Attached context",
                        "author": "Refat",
                        "created_at": "2026-04-10T13:00:00",
                        "is_original": False,
                        "parent_source_key": "refat:101",
                    },
                    {
                        "telegram_message_id": 202,
                        "relevance": "CONTEXT",
                        "reason": "Linked context without provenance",
                        "content": "Unattached context",
                        "author": "Refat",
                        "created_at": "2026-04-10T14:00:00",
                        "is_original": False,
                    },
                ]
            }

    class FakeCommentGroupMapService:
        def __init__(self, **kwargs):
            pass

        def merge_with_main_sources(self, scored_drift_groups, db, expert_id, main_source_ids):
            assert scored_drift_groups == []
            assert expert_id == "refat"
            assert main_source_ids == [101, 102]
            return [
                {
                    "parent_telegram_message_id": 101,
                    "is_main_source_clarification": True,
                    "comments": [
                        {
                            "comment_id": 1,
                            "comment_text": "Author clarification",
                            "author_name": "Refat",
                            "created_at": "2026-04-10T15:00:00",
                            "updated_at": "2026-04-10T15:00:00",
                        }
                    ],
                },
                {
                    "parent_telegram_message_id": 101,
                    "is_main_source_community": True,
                    "comments": [
                        {
                            "comment_id": 2,
                            "comment_text": "Community comment",
                            "author_name": "Reader",
                            "created_at": "2026-04-10T16:00:00",
                            "updated_at": "2026-04-10T16:00:00",
                        }
                    ],
                },
            ]

    async def fail_if_called_async(*args, **kwargs):
        raise AssertionError("Full synthesis pipeline must not be called")

    monkeypatch.setattr(agent_context_module, "MapService", FakeMapService)
    monkeypatch.setattr(agent_context_module, "MediumScoringService", FakeMediumScoringService)
    monkeypatch.setattr(agent_context_module, "SimpleResolveService", FakeResolveService)
    monkeypatch.setattr(agent_context_module, "CommentGroupMapService", FakeCommentGroupMapService)

    from src.services.reduce_service import ReduceService
    from src.services.language_validation_service import LanguageValidationService
    from src.services.comment_synthesis_service import CommentSynthesisService
    from src.services.meta_synthesis_service import MetaSynthesisService
    from src.services.comment_group_map_service import CommentGroupMapService

    monkeypatch.setattr(ReduceService, "process", fail_if_called_async)
    monkeypatch.setattr(LanguageValidationService, "process", fail_if_called_async)
    monkeypatch.setattr(CommentSynthesisService, "process", fail_if_called_async)
    monkeypatch.setattr(MetaSynthesisService, "synthesize", fail_if_called_async)
    monkeypatch.setattr(CommentGroupMapService, "score_drift_groups", fail_if_called_async)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(expert_filter=["refat"]),
        )

    assert response.status_code == 200, response.text
    expert = response.json()["experts"][0]
    assert expert["selected_sources_count"] == 2
    assert [source["telegram_message_id"] for source in expert["main_sources"]] == [101, 102]
    assert all(source["telegram_message_id"] != 103 for source in expert["main_sources"])

    high_source = expert["main_sources"][0]
    assert high_source["source_key"] == "refat:101"
    external_links = high_source["external_links"]
    assert [link["url"] for link in external_links] == [
        "https://github.com/langchain-ai/langgraph",
        "https://example.com/ai-agents-report",
    ]
    assert external_links[0]["label"] == "LangGraph"
    assert external_links[0]["domain"] == "github.com"
    assert external_links[0]["link_type"] == "github_repo"
    assert external_links[0]["fetch_status"] == "not_fetched"
    assert "High content references" in external_links[0]["context"]
    assert external_links[1]["label"] is None
    assert external_links[1]["domain"] == "example.com"
    assert external_links[1]["link_type"] == "web"
    assert external_links[1]["fetch_status"] == "not_fetched"
    assert high_source["linked_context"][0]["telegram_message_id"] == 201
    assert high_source["comments"]["author_comments"][0]["comment_text"] == "Author clarification"
    assert high_source["comments"]["community_comments"][0]["comment_text"] == "Community comment"
    assert high_source["evidence_quality"]["comment_signal"] == "mixed"
    assert high_source["evidence_quality"]["confidence"] in {"medium", "high"}

    medium_source = expert["main_sources"][1]
    assert medium_source["telegram_message_id"] == 102
    assert medium_source["external_links"] == []
    assert medium_source["score"] == 0.91
    assert medium_source["score_reason"] == "Complements the high source"
    assert medium_source["evidence_quality"]["depth"] in {"shallow", "moderate"}

    assert expert["unattached_linked_context"][0]["telegram_message_id"] == 202
    assert "reduce_answer_synthesis" in response.json()["pipeline_skipped"]
    assert "agent_context_source_pipeline_not_implemented" not in response.json()["warnings"]


def test_agent_context_expert_digest_compacts_sources_and_comments(monkeypatch):
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS", 1)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS", 40)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE", 1)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS", 30)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE", 1)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_SIGNALS", 2)
    observed = {"llm_evidence": None}

    async def fake_build_expert_bundle(
        self,
        *,
        expert_id,
        agent_request,
        search_context,
        warnings,
    ):
        return AgentExpertSourceBundle(
            expert_id=expert_id,
            expert_name="Refat",
            channel_username="nobilix",
            selected_sources_count=2,
            unattached_linked_context=[
                AgentLinkedContext(
                    telegram_message_id=301,
                    source_key="refat:301",
                    source_role="context",
                    relevance="CONTEXT",
                    content="Unattached linked context",
                )
            ],
            main_sources=[
                AgentMainSource(
                    telegram_message_id=101,
                    source_key="refat:101",
                    relevance="HIGH",
                    reason="Direct practitioner signal",
                    content=(
                        "Long source content about subagents, context hygiene, "
                        "and memory boundaries that should be clipped."
                    ),
                    linked_context=[
                        AgentLinkedContext(
                            telegram_message_id=201,
                            source_key="refat:201",
                            source_role="context",
                            relevance="CONTEXT",
                            content="Attached linked context",
                        )
                    ],
                    external_links=[
                        AgentExternalLink(
                            url="https://github.com/example/agent-tool",
                            domain="github.com",
                            link_type="github_repo",
                            fetch_status="not_fetched",
                        ),
                        AgentExternalLink(
                            url="https://example.com/report",
                            domain="example.com",
                            link_type="web",
                            fetch_status="not_fetched",
                        ),
                    ],
                    comments=AgentSourceComments(
                        author_comments=[
                            AgentSourceComment(
                                comment_id=1,
                                comment_text="Author clarification should be clipped",
                                author_name="Refat",
                            ),
                            AgentSourceComment(
                                comment_id=2,
                                comment_text="Second author clarification",
                                author_name="Refat",
                            ),
                        ],
                        community_comments=[
                            AgentSourceComment(
                                comment_id=3,
                                comment_text="Community observation",
                                author_name="Reader",
                            )
                        ],
                    ),
                ),
                AgentMainSource(
                    telegram_message_id=102,
                    source_key="refat:102",
                    relevance="MEDIUM",
                    reason="Secondary practitioner signal",
                    content="Secondary content",
                ),
            ],
        )

    async def fake_call_llm_digest(self, *, query, bundle, evidence):
        observed["llm_evidence"] = evidence
        return {
            "position": "Refat frames subagents as explicit bounded helpers.",
            "key_signals": [
                {
                    "claim": "Use subagents when selection and scope are explicit.",
                    "support_level": "direct",
                    "supporting_sources": ["refat:101", "refat:999"],
                    "comment_signal": "Author comment clarifies the boundary.",
                    "limits": "Practitioner opinion, not benchmark evidence.",
                }
            ],
            "limits": ["Only capped source refs were sent to the reducer."],
        }

    monkeypatch.setattr(
        AgentContextService,
        "_build_expert_bundle",
        fake_build_expert_bundle,
    )
    monkeypatch.setattr(
        AgentExpertDigestReducer,
        "_call_llm_digest",
        fake_call_llm_digest,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(
                response_mode="expert_digest",
                expert_filter=["refat"],
            ),
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "expert_digest"
    assert "expert_digest_reduce" in payload["pipeline_used"]
    assert "reduce_answer_synthesis" in payload["pipeline_skipped"]

    expert = payload["experts"][0]
    assert expert["selected_sources_count"] == 2
    assert expert["main_sources"] == []
    assert expert["unattached_linked_context"] == []
    assert "comment_id" not in json.dumps(expert)

    digest = expert["digest"]
    assert digest["position"] == "Refat frames subagents as explicit bounded helpers."
    assert digest["source_refs"][0]["source_key"] == "refat:101"
    assert digest["source_refs"][0]["evidence_quality"]["comment_signal"] == "mixed"
    assert digest["source_refs"][0]["short_excerpt"].endswith("...")
    assert [source["source_key"] for source in digest["source_index"]] == [
        "refat:101",
        "refat:102",
    ]
    assert digest["source_index"][0]["evidence_quality"]["comment_signal"] == "mixed"
    assert digest["source_index"][1]["evidence_quality"]["depth"] in {
        "shallow",
        "moderate",
    }
    assert digest["source_index"][0]["content_chars"] > 0
    assert digest["source_index"][0]["external_links_count"] == 2
    assert digest["source_index"][1]["external_links_count"] == 0
    assert len(digest["source_refs"][0]["external_links"]) == 1
    assert digest["source_refs"][0]["external_links"][0]["fetch_status"] == "not_fetched"
    assert digest["comments_digest"]["author_comments_count"] == 2
    assert digest["comments_digest"]["community_comments_count"] == 1
    assert len(digest["comments_digest"]["included_comments"]) == 1
    assert digest["comments_digest"]["omitted_comments_count"] == 2
    assert digest["omitted_counts"] == {
        "main_sources": 1,
        "linked_context": 1,
        "author_comments": 1,
        "community_comments": 1,
        "external_links": 1,
    }
    assert digest["limits_used"] == {
        "max_source_refs": 1,
        "max_source_chars": 40,
        "max_comments_per_source": 1,
        "max_comment_chars": 30,
        "max_links_per_source": 1,
        "max_signals": 2,
        "source_index_scope": "all_selected_sources",
    }
    assert digest["key_signals"][0]["supporting_sources"] == ["refat:101"]
    assert observed["llm_evidence"]["source_refs"][0]["source_key"] == "refat:101"
    assert observed["llm_evidence"]["source_refs"][0]["evidence_quality"]["comment_signal"] == "mixed"
    assert len(observed["llm_evidence"]["source_refs"]) == 1


def test_agent_context_expert_digest_defaults_do_not_drop_sources_comments_or_signals(
    monkeypatch,
):
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_SOURCE_REFS", 0)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_SOURCE_CHARS", 0)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_COMMENTS_PER_SOURCE", 0)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_COMMENT_CHARS", 0)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_LINKS_PER_SOURCE", 0)
    monkeypatch.setattr(config, "AGENT_CONTEXT_DIGEST_MAX_SIGNALS", 0)
    observed = {"llm_evidence": None}

    async def fake_build_expert_bundle(
        self,
        *,
        expert_id,
        agent_request,
        search_context,
        warnings,
    ):
        return AgentExpertSourceBundle(
            expert_id=expert_id,
            expert_name="Refat",
            channel_username="nobilix",
            selected_sources_count=2,
            main_sources=[
                AgentMainSource(
                    telegram_message_id=101,
                    source_key="refat:101",
                    relevance="HIGH",
                    reason="First source",
                    content="First full source content that should not be clipped.",
                    comments=AgentSourceComments(
                        community_comments=[
                            AgentSourceComment(
                                comment_id=1,
                                comment_text="First full comment that should not be clipped.",
                                author_name="Reader",
                            ),
                            AgentSourceComment(
                                comment_id=2,
                                comment_text="Second full comment that should not be dropped.",
                                author_name="Reader",
                            ),
                        ],
                    ),
                ),
                AgentMainSource(
                    telegram_message_id=102,
                    source_key="refat:102",
                    relevance="HIGH",
                    reason="Second source",
                    content="Second full source content.",
                    external_links=[
                        AgentExternalLink(
                            url="https://example.com/a",
                            domain="example.com",
                            fetch_status="not_fetched",
                        ),
                        AgentExternalLink(
                            url="https://example.com/b",
                            domain="example.com",
                            fetch_status="not_fetched",
                        ),
                    ],
                ),
            ],
        )

    async def fake_call_llm_digest(self, *, query, bundle, evidence):
        observed["llm_evidence"] = evidence
        return {
            "position": "Full backend digest.",
            "key_signals": [
                {
                    "claim": "Signal one.",
                    "support_level": "direct",
                    "supporting_sources": ["refat:101"],
                },
                {
                    "claim": "Signal two.",
                    "support_level": "direct",
                    "supporting_sources": ["refat:102"],
                },
                {
                    "claim": "Signal three.",
                    "support_level": "direct",
                    "supporting_sources": ["refat:101"],
                },
            ],
            "limits": [
                "First limit.",
                "Second limit.",
                "Third limit.",
                "Fourth limit.",
                "Fifth limit.",
                "Sixth limit must not be dropped.",
            ],
        }

    monkeypatch.setattr(
        AgentContextService,
        "_build_expert_bundle",
        fake_build_expert_bundle,
    )
    monkeypatch.setattr(
        AgentExpertDigestReducer,
        "_call_llm_digest",
        fake_call_llm_digest,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(
                response_mode="expert_digest",
                expert_filter=["refat"],
            ),
        )

    assert response.status_code == 200, response.text
    digest = response.json()["experts"][0]["digest"]
    assert [source["source_key"] for source in digest["source_refs"]] == [
        "refat:101",
        "refat:102",
    ]
    assert digest["source_refs"][0]["short_excerpt"] == (
        "First full source content that should not be clipped."
    )
    assert len(digest["source_refs"][1]["external_links"]) == 2
    assert len(digest["comments_digest"]["included_comments"]) == 2
    assert digest["omitted_counts"]["main_sources"] == 0
    assert digest["omitted_counts"]["community_comments"] == 0
    assert len(digest["key_signals"]) == 3
    assert digest["limits"][-1] == "Sixth limit must not be dropped."
    assert len(observed["llm_evidence"]["source_refs"]) == 2
    assert len(observed["llm_evidence"]["comments"]["included_comments"]) == 2


def test_agent_context_expert_digest_accepts_top_level_signal_list():
    reducer = AgentExpertDigestReducer()
    bundle = AgentExpertSourceBundle(
        expert_id="refat",
        expert_name="Refat",
        channel_username="nobilix",
        selected_sources_count=1,
    )
    source_refs = [
        AgentDigestSourceRef(
            telegram_message_id=101,
            source_key="refat:101",
            relevance="HIGH",
        )
    ]

    digest = reducer._normalize_llm_digest(
        data=[
            {
                "claim": "Use subagents for explicit bounded work.",
                "support_level": "direct",
                "supporting_sources": ["refat:101"],
            }
        ],
        bundle=bundle,
        source_index=[],
        source_refs=source_refs,
        comments_digest=AgentDigestComments(),
        omitted_counts=AgentDigestOmittedCounts(),
    )

    assert digest.key_signals[0].claim == "Use subagents for explicit bounded work."
    assert digest.key_signals[0].supporting_sources == ["refat:101"]
    assert digest.position == (
        "Refat has source-backed signals for this query, but the digest reducer "
        "did not return a separate stance summary."
    )


def test_agent_context_expand_returns_raw_source_without_search_pipeline(monkeypatch):
    observed = {"comment_source_ids": []}

    async def fail_if_called_async(*args, **kwargs):
        raise AssertionError("source_expand must not call search or synthesis pipeline")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("source_expand must not call search or synthesis pipeline")

    fake_post = SimpleNamespace(
        expert_id="refat",
        telegram_message_id=101,
        message_text=(
            "Refat raw source about source expansion with "
            "[LangGraph](https://github.com/langchain-ai/langgraph) and extra detail."
        ),
        author_name="Refat",
        created_at=datetime.fromisoformat("2026-04-10T12:00:00"),
    )

    def fake_load_post_by_source_key(self, expert_id, telegram_message_id):
        assert expert_id == "refat"
        assert telegram_message_id == 101
        return fake_post

    class FakeCommentGroupMapService:
        def __init__(self, **kwargs):
            pass

        def merge_with_main_sources(self, scored_drift_groups, db, expert_id, main_source_ids):
            assert scored_drift_groups == []
            assert expert_id == "refat"
            assert main_source_ids == [101]
            observed["comment_source_ids"].extend(main_source_ids)
            return [
                {
                    "parent_telegram_message_id": 101,
                    "is_main_source_clarification": True,
                    "comments": [
                        {
                            "comment_id": 1,
                            "comment_text": "Author clarification",
                            "author_name": "Refat",
                            "created_at": "2026-04-10T15:00:00",
                            "updated_at": "2026-04-10T15:00:00",
                        }
                    ],
                },
                {
                    "parent_telegram_message_id": 101,
                    "is_main_source_community": True,
                    "comments": [
                        {
                            "comment_id": 2,
                            "comment_text": "Community comment",
                            "author_name": "Reader",
                            "created_at": "2026-04-10T16:00:00",
                            "updated_at": "2026-04-10T16:00:00",
                        }
                    ],
                },
            ]

    monkeypatch.setattr(AgentContextService, "_prepare_search_context", fail_if_called_async)
    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts_with_embeddings",
        fail_if_called_async,
    )
    monkeypatch.setattr(AgentContextService, "_load_post_by_source_key", fake_load_post_by_source_key)
    monkeypatch.setattr(agent_context_module, "MapService", fail_if_called)
    monkeypatch.setattr(agent_context_module, "MediumScoringService", fail_if_called)
    monkeypatch.setattr(agent_context_module, "SimpleResolveService", fail_if_called)
    monkeypatch.setattr(agent_context_module, "CommentGroupMapService", FakeCommentGroupMapService)
    monkeypatch.setattr(AgentExpertDigestReducer, "compact_bundle", fail_if_called_async)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context/expand",
            headers=_auth_headers(),
            json={
                "source_keys": ["refat:101"],
                "max_content_chars": 48,
                "max_comments_per_source": 2,
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "source_expand"
    assert payload["limits_used"] == {
        "include_comments": True,
        "include_external_links": True,
        "max_content_chars": 48,
        "max_comments_per_source": 2,
    }
    assert payload["not_found"] == []
    assert payload["warnings"] == []
    assert observed["comment_source_ids"] == [101]

    source = payload["sources"][0]
    assert source["source_key"] == "refat:101"
    assert source["expert_id"] == "refat"
    assert source["telegram_message_id"] == 101
    assert source["content"].endswith("...")
    assert source["truncation"]["content_truncated"] is True
    assert source["truncation"]["comments_truncated"] is False
    assert source["external_links"][0]["domain"] == "github.com"
    assert source["external_links"][0]["fetch_status"] == "not_fetched"
    assert source["comments"]["author_comments"][0]["comment_text"] == "Author clarification"
    assert source["comments"]["community_comments"][0]["comment_text"] == "Community comment"
    assert source["evidence_quality"]["comment_signal"] == "mixed"
    assert source["evidence_quality"]["confidence"] in {"medium", "high"}


def test_agent_context_expand_artifact_endpoint_saves_exact_source_result(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        config,
        "AGENT_CONTEXT_RESULTS_DIR",
        str(tmp_path / "agent-context-results"),
    )
    fake_post = SimpleNamespace(
        expert_id="refat",
        telegram_message_id=101,
        message_text="Refat raw source about exact expansion.",
        author_name="Refat",
        created_at=datetime.fromisoformat("2026-04-10T12:00:00"),
    )
    monkeypatch.setattr(
        AgentContextService,
        "_load_post_by_source_key",
        lambda self, expert_id, telegram_message_id: fake_post,
    )

    with TestClient(app) as client:
        receipt_response = client.post(
            "/api/v1/agent/context/expand/artifact",
            headers=_auth_headers(),
            json={
                "source_keys": ["refat:101"],
                "include_comments": False,
                "max_content_chars": 100,
            },
        )
        assert receipt_response.status_code == 200, receipt_response.text
        receipt = receipt_response.json()
        assert receipt["kind"] == "agent_context_artifact"
        assert receipt["operation"] == "expand"
        assert receipt["mode"] == "source_expand"
        assert receipt["source_keys"] == ["refat:101"]

        result_response = client.get(receipt["result_url"], headers=_auth_headers())

    assert result_response.status_code == 200, result_response.text
    payload = result_response.json()
    assert payload["request_id"] == receipt["request_id"]
    assert payload["mode"] == "source_expand"
    assert payload["sources"][0]["source_key"] == "refat:101"


def test_agent_context_evidence_quality_calibration_distinguishes_practical_sources_from_announcements():
    service = AgentContextService.__new__(AgentContextService)
    practical_source = AgentMainSource(
        telegram_message_id=701,
        source_key="refat:701",
        relevance="HIGH",
        reason="Direct practitioner signal from production experience",
        content=(
            "In production we used subagents for bounded codebase research. "
            "The practical lesson is to give each helper a narrow scope, a clear "
            "handoff, and source-backed output. The tradeoff is coordination cost, "
            "so I use them only when parallel investigation saves time and the "
            "parent agent can verify the claims against files and tests."
        ),
        comments=AgentSourceComments(
            author_comments=[
                AgentSourceComment(
                    comment_id=1,
                    comment_text="Author clarification: this worked only with explicit scope.",
                    author_name="Refat",
                )
            ]
        ),
    )
    announcement_source = AgentMainSource(
        telegram_message_id=702,
        source_key="refat:702",
        relevance="MEDIUM",
        reason="Secondary mention of a tool announcement",
        content="Launch: a new agent helper is out. Link in the post.",
    )

    service._refresh_evidence_quality([practical_source, announcement_source])

    assert practical_source.evidence_quality.depth == "deep_practical"
    assert practical_source.evidence_quality.source_type == "practitioner_experience"
    assert practical_source.evidence_quality.comment_signal == "author_support"
    assert practical_source.evidence_quality.confidence == "high"
    assert announcement_source.evidence_quality.depth == "shallow"
    assert announcement_source.evidence_quality.source_type == "announcement"
    assert announcement_source.evidence_quality.confidence == "low"


def test_agent_context_expand_missing_source_goes_to_not_found(monkeypatch):
    monkeypatch.setattr(
        AgentContextService,
        "_load_post_by_source_key",
        lambda self, expert_id, telegram_message_id: None,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context/expand",
            headers=_auth_headers(),
            json={"source_keys": ["refat:999"]},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "source_expand"
    assert payload["sources"] == []
    assert payload["not_found"] == ["refat:999"]


def test_agent_context_expand_rejects_invalid_source_key():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context/expand",
            headers=_auth_headers(),
            json={"source_keys": ["not-a-source-key"]},
        )

    assert response.status_code == 400, response.text
    assert "source_key must use" in response.json()["message"]


def test_agent_context_external_link_extraction_handles_telegram_markdown_edges():
    service = AgentContextService.__new__(AgentContextService)
    content = (
        "Stack **vLLM**M](https://github.com/vllm-project/vllm)** and "
        "LiteLLM**M](https://github.com/BerriAI/litellm)** plus "
        "[round-robin](https://ru.wikipedia.org/wiki/"
        "Round-robin_(%D0%B0%D0%BB%D0%B3%D0%BE%D1%80%D0%B8%D1%82%D0%BC))"
    )

    links = service._extract_external_links(content)

    assert [link.url for link in links] == [
        "https://ru.wikipedia.org/wiki/Round-robin_(%D0%B0%D0%BB%D0%B3%D0%BE%D1%80%D0%B8%D1%82%D0%BC)",
        "https://github.com/vllm-project/vllm",
        "https://github.com/BerriAI/litellm",
    ]
    assert links[0].label == "round-robin"
    assert all(link.fetch_status == "not_fetched" for link in links)
    assert all(not link.url.endswith(")**") for link in links)


def test_agent_context_can_skip_main_source_comments(monkeypatch):
    posts = [_fake_post(101, "2026-04-10T12:00:00")]

    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts",
        lambda self, expert_id, cutoff_date=None: posts,
    )

    class FakeMapService:
        def __init__(self, **kwargs):
            pass

        async def process(self, **kwargs):
            return {
                "relevant_posts": [
                    {
                        "telegram_message_id": 101,
                        "relevance": "HIGH",
                        "reason": "Direct match",
                    }
                ]
            }

    class FakeMediumScoringService:
        def __init__(self, **kwargs):
            pass

    class FakeResolveService:
        async def process(self, **kwargs):
            return {
                "enriched_posts": [
                    {
                        "telegram_message_id": 101,
                        "relevance": "HIGH",
                        "reason": "Direct match",
                        "content": "High content",
                        "author": "Refat",
                        "created_at": "2026-04-10T12:00:00",
                        "is_original": True,
                    }
                ]
            }

    class FailingCommentGroupMapService:
        def __init__(self, **kwargs):
            raise AssertionError("Comment loader should not be instantiated")

    monkeypatch.setattr(agent_context_module, "MapService", FakeMapService)
    monkeypatch.setattr(agent_context_module, "MediumScoringService", FakeMediumScoringService)
    monkeypatch.setattr(agent_context_module, "SimpleResolveService", FakeResolveService)
    monkeypatch.setattr(agent_context_module, "CommentGroupMapService", FailingCommentGroupMapService)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/context",
            headers=_auth_headers(),
            json=_agent_context_payload(
                expert_filter=["refat"],
                include_main_source_comments=False,
            ),
        )

    assert response.status_code == 200, response.text
    source = response.json()["experts"][0]["main_sources"][0]
    assert source["comments"] == {"author_comments": [], "community_comments": []}
    assert "main_source_comments" in response.json()["pipeline_skipped"]


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
