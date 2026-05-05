#!/usr/bin/env python3
"""BDD acceptance tests for the explicit Agent Context CLI -> API flow."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src import config
from src.api import dependencies
from src.api.main import app
from src.cli import agent_context
from src.services import agent_context_service as agent_context_module
from src.services import health_probe_service as health_probe_module
from src.services.agent_context_service import AgentContextSearchContext, AgentContextService


class FakeHealthProbeService:
    async def warm_cache(self):
        return {}


class RequestsLikeResponse:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.text = response.text

    def json(self):
        return self._response.json()

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


@pytest.fixture(autouse=True)
def agent_context_acceptance_config(monkeypatch):
    fake_health_service = FakeHealthProbeService()
    monkeypatch.setattr(
        health_probe_module,
        "get_health_probe_service",
        lambda: fake_health_service,
    )
    given_agent_context_token(monkeypatch, token="acceptance-token")
    monkeypatch.setenv(
        "AGENT_CONTEXT_API_URL",
        "http://testserver/api/v1/agent/context",
    )
    monkeypatch.setenv("AGENT_CONTEXT_TIMEOUT_SECONDS", "90")
    monkeypatch.setattr(config, "AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE", 100)
    monkeypatch.setattr(config, "AGENT_CONTEXT_TIMEOUT_SECONDS", 90)
    monkeypatch.setattr(config, "AGENT_CONTEXT_MAX_RESPONSE_BYTES", 500000)
    monkeypatch.setattr(
        AgentContextService,
        "_get_expert_metadata",
        lambda self, expert_id: {
            "expert_name": expert_id.title(),
            "channel_username": f"{expert_id}_channel",
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


def given_agent_context_token(monkeypatch, *, token: str):
    monkeypatch.setenv("AGENT_CONTEXT_API_TOKEN", token)
    monkeypatch.setattr(config, "AGENT_CONTEXT_API_TOKEN", token)
    return token


def given_source_bundle_pipeline_fakes(monkeypatch):
    observed = {
        "loaded_expert_ids": [],
        "map_expert_ids": [],
        "medium_scoring_expert_ids": [],
        "resolve_expert_ids": [],
        "comment_expert_ids": [],
    }

    def fake_load_candidate_posts(self, expert_id, cutoff_date=None):
        observed["loaded_expert_ids"].append(expert_id)
        return [
            _fake_post(101, expert_id, "2026-04-10T12:00:00"),
            _fake_post(102, expert_id, "2026-04-09T12:00:00"),
            _fake_post(103, expert_id, "2026-04-08T12:00:00"),
        ]

    class FakeMapService:
        def __init__(self, **kwargs):
            pass

        async def process(self, **kwargs):
            expert_id = kwargs["expert_id"]
            observed["map_expert_ids"].append(expert_id)
            return {
                "relevant_posts": [
                    {
                        "telegram_message_id": 101,
                        "relevance": "HIGH",
                        "reason": f"Direct match for {expert_id}",
                    },
                    {
                        "telegram_message_id": 102,
                        "relevance": "MEDIUM",
                        "reason": f"Useful secondary source for {expert_id}",
                    },
                    {
                        "telegram_message_id": 103,
                        "relevance": "LOW",
                        "reason": f"Too broad for {expert_id}",
                    },
                ]
            }

    class FakeMediumScoringService:
        def __init__(self, **kwargs):
            pass

        async def score_medium_posts(self, medium_posts, **kwargs):
            observed["medium_scoring_expert_ids"].append(kwargs["expert_id"])
            return [
                {
                    **medium_posts[0],
                    "score": 0.91,
                    "score_reason": "Complements the high source",
                }
            ]

    class FakeResolveService:
        async def process(self, **kwargs):
            expert_id = kwargs["expert_id"]
            observed["resolve_expert_ids"].append(expert_id)
            return {
                "enriched_posts": [
                    {
                        "telegram_message_id": 101,
                        "relevance": "HIGH",
                        "reason": f"Direct match for {expert_id}",
                        "content": (
                            f"High source from {expert_id} cites "
                            "[LangGraph](https://github.com/langchain-ai/langgraph) "
                            "and https://example.com/agent-context."
                        ),
                        "author": expert_id.title(),
                        "created_at": "2026-04-10T12:00:00",
                        "is_original": True,
                    },
                    {
                        "telegram_message_id": 201,
                        "relevance": "CONTEXT",
                        "reason": f"Attached context for {expert_id}",
                        "content": f"Attached context from {expert_id}",
                        "author": expert_id.title(),
                        "created_at": "2026-04-10T13:00:00",
                        "is_original": False,
                        "parent_source_key": f"{expert_id}:101",
                    },
                    {
                        "telegram_message_id": 202,
                        "relevance": "CONTEXT",
                        "reason": f"Unattached context for {expert_id}",
                        "content": f"Unattached context from {expert_id}",
                        "author": expert_id.title(),
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
            assert set(main_source_ids) == {101, 102}
            observed["comment_expert_ids"].append(expert_id)
            return [
                {
                    "parent_telegram_message_id": 101,
                    "is_main_source_clarification": True,
                    "comments": [
                        {
                            "comment_id": 1,
                            "comment_text": f"Author clarification from {expert_id}",
                            "author_name": expert_id.title(),
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
                            "comment_text": f"Community comment under {expert_id}",
                            "author_name": "Reader",
                            "created_at": "2026-04-10T16:00:00",
                            "updated_at": "2026-04-10T16:00:00",
                        }
                    ],
                },
            ]

    monkeypatch.setattr(
        AgentContextService,
        "_load_candidate_posts",
        fake_load_candidate_posts,
    )
    monkeypatch.setattr(agent_context_module, "MapService", FakeMapService)
    monkeypatch.setattr(
        agent_context_module,
        "MediumScoringService",
        FakeMediumScoringService,
    )
    monkeypatch.setattr(
        agent_context_module,
        "SimpleResolveService",
        FakeResolveService,
    )
    monkeypatch.setattr(
        agent_context_module,
        "CommentGroupMapService",
        FakeCommentGroupMapService,
    )
    given_full_synthesis_pipeline_would_fail_if_called(monkeypatch)
    return observed


def given_full_synthesis_pipeline_would_fail_if_called(monkeypatch):
    async def fail_if_called_async(*args, **kwargs):
        raise AssertionError("Full synthesis pipeline must not be called")

    from src.services.comment_group_map_service import CommentGroupMapService
    from src.services.comment_synthesis_service import CommentSynthesisService
    from src.services.language_validation_service import LanguageValidationService
    from src.services.meta_synthesis_service import MetaSynthesisService
    from src.services.reduce_service import ReduceService

    monkeypatch.setattr(ReduceService, "process", fail_if_called_async)
    monkeypatch.setattr(LanguageValidationService, "process", fail_if_called_async)
    monkeypatch.setattr(CommentSynthesisService, "process", fail_if_called_async)
    monkeypatch.setattr(MetaSynthesisService, "synthesize", fail_if_called_async)
    monkeypatch.setattr(
        CommentGroupMapService,
        "score_drift_groups",
        fail_if_called_async,
    )


def when_cli_calls_agent_context(monkeypatch, capsys, argv):
    http_calls = []

    with TestClient(app) as client:
        def fake_post(url, *, headers, json, timeout):
            http_calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": timeout,
                }
            )
            response = client.post(
                "/api/v1/agent/context",
                headers=headers,
                json=json,
            )
            return RequestsLikeResponse(response)

        monkeypatch.setattr(agent_context.requests, "post", fake_post)
        exit_code = agent_context.main(argv, load_env=False)

    captured = capsys.readouterr()
    return SimpleNamespace(
        exit_code=exit_code,
        stdout=captured.out,
        stderr=captured.err,
        http_calls=http_calls,
    )


def then_cli_succeeded(result):
    assert result.exit_code == 0, result.stderr


def then_cli_failed_with_actionable_api_message(result, expected_message):
    assert result.exit_code == 1
    assert "Agent Context API returned HTTP" in result.stderr
    assert expected_message in result.stderr


def _fake_post(telegram_message_id: int, expert_id: str, created_at: str):
    return SimpleNamespace(
        telegram_message_id=telegram_message_id,
        message_text=(
            f"{expert_id} post {telegram_message_id} content long enough for retrieval"
        ),
        author_name=expert_id.title(),
        created_at=datetime.fromisoformat(created_at),
    )


def _raw_payload(result):
    return json.loads(result.stdout)


def test_acceptance_custom_experts_flow_from_cli_to_source_bundle(monkeypatch, capsys):
    observed = given_source_bundle_pipeline_fakes(monkeypatch)

    result = when_cli_calls_agent_context(
        monkeypatch,
        capsys,
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "refat,akimov",
        ],
    )

    then_cli_succeeded(result)
    assert len(result.http_calls) == 1
    assert result.http_calls[0]["json"]["expert_scope"] == "custom"
    assert result.http_calls[0]["json"]["expert_filter"] == ["refat", "akimov"]
    assert observed["loaded_expert_ids"] == ["refat", "akimov"]
    assert observed["map_expert_ids"] == ["refat", "akimov"]
    assert observed["resolve_expert_ids"] == ["refat", "akimov"]
    assert "expert_scope: custom" in result.stdout
    assert "expert_filter: [\"refat\", \"akimov\"]" in result.stdout
    assert "refat (@refat_channel)" in result.stdout
    assert "akimov (@akimov_channel)" in result.stdout
    assert result.stdout.count("selected_sources_count: 2") == 2
    assert "101 [HIGH] Direct match for refat" in result.stdout
    assert "101 [HIGH] Direct match for akimov" in result.stdout


def test_acceptance_safe_defaults_survive_cli_http_api_boundary(monkeypatch, capsys):
    given_source_bundle_pipeline_fakes(monkeypatch)

    result = when_cli_calls_agent_context(
        monkeypatch,
        capsys,
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "refat",
            "--json",
        ],
    )

    then_cli_succeeded(result)
    request_body = result.http_calls[0]["json"]
    assert request_body == {
        "query": "AI agents for sales",
        "response_mode": "source_bundle",
        "expert_scope": "custom",
        "expert_group": None,
        "expert_filter": ["refat"],
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": False,
        "use_super_passport": True,
    }

    response_payload = _raw_payload(result)
    assert response_payload["selection_used"] == {
        "expert_scope": "custom",
        "expert_group": None,
        "expert_filter": ["refat"],
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": False,
        "use_super_passport": True,
    }
    assert response_payload["reddit"] is None
    assert "source_selection" in response_payload["pipeline_used"]
    assert "reduce_answer_synthesis" in response_payload["pipeline_skipped"]
    assert "drift_comment_group_scoring" in response_payload["pipeline_skipped"]
    assert "comment_synthesis" in response_payload["pipeline_skipped"]
    assert "cross_expert_meta_synthesis" in response_payload["pipeline_skipped"]


def test_acceptance_cli_path_does_not_call_full_synthesis_pipeline(monkeypatch, capsys):
    observed = given_source_bundle_pipeline_fakes(monkeypatch)

    result = when_cli_calls_agent_context(
        monkeypatch,
        capsys,
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "refat",
            "--json",
        ],
    )

    then_cli_succeeded(result)
    response_payload = _raw_payload(result)
    assert observed["comment_expert_ids"] == ["refat"]
    assert response_payload["experts"][0]["selected_sources_count"] == 2
    assert "source_bundle_failed" not in json.dumps(response_payload)
    assert response_payload["pipeline_skipped"] == [
        "reduce_answer_synthesis",
        "language_validation",
        "drift_comment_group_scoring",
        "comment_synthesis",
        "cross_expert_meta_synthesis",
        "reddit_synthesis",
    ]


def test_acceptance_source_evidence_shape_is_agent_readable(monkeypatch, capsys):
    given_source_bundle_pipeline_fakes(monkeypatch)

    result = when_cli_calls_agent_context(
        monkeypatch,
        capsys,
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "refat",
            "--json",
        ],
    )

    then_cli_succeeded(result)
    expert = _raw_payload(result)["experts"][0]
    assert expert["expert_id"] == "refat"
    assert expert["selected_sources_count"] == 2
    assert [source["telegram_message_id"] for source in expert["main_sources"]] == [
        101,
        102,
    ]
    assert 103 not in [
        source["telegram_message_id"] for source in expert["main_sources"]
    ]

    high_source = expert["main_sources"][0]
    assert high_source["source_key"] == "refat:101"
    assert high_source["source_role"] == "main"
    assert high_source["relevance"] == "HIGH"
    assert [link["url"] for link in high_source["external_links"]] == [
        "https://github.com/langchain-ai/langgraph",
        "https://example.com/agent-context",
    ]
    assert high_source["external_links"][0]["fetch_status"] == "not_fetched"
    assert high_source["external_links"][0]["link_type"] == "github_repo"
    assert high_source["linked_context"][0]["telegram_message_id"] == 201
    assert high_source["linked_context"][0]["parent_source_key"] == "refat:101"
    assert high_source["comments"]["author_comments"][0]["comment_text"] == (
        "Author clarification from refat"
    )
    assert high_source["comments"]["community_comments"][0]["comment_text"] == (
        "Community comment under refat"
    )

    medium_source = expert["main_sources"][1]
    assert medium_source["telegram_message_id"] == 102
    assert medium_source["relevance"] == "MEDIUM"
    assert medium_source["score"] == 0.91
    assert medium_source["score_reason"] == "Complements the high source"

    assert expert["unattached_linked_context"][0]["telegram_message_id"] == 202
    assert expert["unattached_linked_context"][0]["source_role"] == "context"


def test_acceptance_token_stays_out_of_body_and_cli_output(monkeypatch, capsys):
    secret_token = given_agent_context_token(monkeypatch, token="super-secret-token")
    given_source_bundle_pipeline_fakes(monkeypatch)

    result = when_cli_calls_agent_context(
        monkeypatch,
        capsys,
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "refat",
            "--json",
        ],
    )

    then_cli_succeeded(result)
    request = result.http_calls[0]
    assert request["headers"] == {"Authorization": f"Bearer {secret_token}"}
    assert secret_token not in json.dumps(request["json"], ensure_ascii=False)
    assert secret_token not in result.stdout
    assert secret_token not in result.stderr


def test_acceptance_unsupported_video_hub_failure_is_actionable(monkeypatch, capsys):
    result = when_cli_calls_agent_context(
        monkeypatch,
        capsys,
        [
            "--query",
            "AI agents for sales",
            "--experts",
            "video_hub",
        ],
    )

    then_cli_failed_with_actionable_api_message(
        result,
        "video_hub source_bundle is not implemented",
    )
    assert result.http_calls[0]["json"]["expert_filter"] == ["video_hub"]
    assert "acceptance-token" not in result.stdout
    assert "acceptance-token" not in result.stderr
