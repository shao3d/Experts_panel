#!/usr/bin/env python3
"""Targeted tests for the Agent Context API MVP skeleton."""

import os
import sys
import asyncio
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
from src.services.agent_context_service import AgentContextSearchContext, AgentContextService
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
    assert expert_ids == (
        AGENT_CONTEXT_EXPERT_GROUPS["tech"]
        + AGENT_CONTEXT_EXPERT_GROUPS["tech_business"]
    )
    assert response.json()["selection_used"]["expert_filter"] is None


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
                        "content": "High content",
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
    assert high_source["linked_context"][0]["telegram_message_id"] == 201
    assert high_source["comments"]["author_comments"][0]["comment_text"] == "Author clarification"
    assert high_source["comments"]["community_comments"][0]["comment_text"] == "Community comment"

    medium_source = expert["main_sources"][1]
    assert medium_source["telegram_message_id"] == 102
    assert medium_source["score"] == 0.91
    assert medium_source["score_reason"] == "Complements the high source"

    assert expert["unattached_linked_context"][0]["telegram_message_id"] == 202
    assert "reduce_answer_synthesis" in response.json()["pipeline_skipped"]
    assert "agent_context_source_pipeline_not_implemented" not in response.json()["warnings"]


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
