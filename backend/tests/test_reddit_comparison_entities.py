"""Comparison-entity extraction: the query a comparison search actually sends.

Measured 2026-10-18: `comparison_anchor_relevance` sends
``anchor_terms[0] anchor_terms[1] benchmark``, and the anchor heuristic ranks
by shape, not by entity — real owner questions produced "5.3 good benchmark",
"deepseek intel benchmark" and "code benchmark". These tests pin the
replacement formulation: name-shaped runs, split at the comparison marker.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.services.reddit_enhanced_service import (  # noqa: E402
    _entity_runs,
    _extract_comparison_entities,
)


def test_marker_split_keeps_one_entity_per_side():
    entities = _extract_comparison_entities(
        "Xiaomi MiMo V2.6 Pro vs GLM-5.3 Flash comparison"
    )
    assert entities[:2] == ["Xiaomi MiMo V2.6 Pro", "GLM-5.3 Flash"]


def test_model_tier_suffix_is_not_a_second_product():
    """"GLM-5.3 Flash" is one entity; gluing the next brand on is the bug."""
    entities = _extract_comparison_entities("GLM-5.3 Flash vs DeepSeek V4.1 Flash")
    assert entities[:2] == ["GLM-5.3 Flash", "DeepSeek V4.1 Flash"]


def test_multi_model_value_question_lists_models_not_prose():
    entities = _extract_comparison_entities(
        "best value LLM models GLM-5.3 Kimi K3 Qwen 3.8 Max"
    )
    assert "GLM-5.3" in entities
    assert "Kimi K3" in entities
    assert "Qwen 3.8 Max" in entities
    assert all(entity.lower() != "best value" for entity in entities)


def test_version_token_attaches_to_its_brand():
    entities = _extract_comparison_entities(
        "best value models GLM-5.3 Flash GPT-5.6 Sol DeepSeek V4.1"
    )
    assert "GLM-5.3 Flash" in entities
    assert "DeepSeek V4.1" in entities


def test_sentence_opener_is_not_an_entity():
    """'There is a project called dsh-cli' must not yield the entity 'There'."""
    entities = _extract_comparison_entities(
        "There is a project called 'dsh-cli' - a native TUI client for DeepSeek"
    )
    assert "There" not in entities


def test_control_query_that_motivated_the_change_is_not_produced():
    """The old formulation's measured failures must not come back."""
    for query in (
        "Is Thinking Machines' Inkling model as good as GLM 5.3 in practice?",
        "OpenAI GPT Image 2.5 Sunburst versus Flare Codex routing",
    ):
        joined = " ".join(_extract_comparison_entities(query)).lower()
        assert "good benchmark" not in joined
        assert not joined.startswith("5.3 good")


def test_single_entity_question_yields_no_pair():
    """A 'comparison' question with nothing to compare must not fabricate one."""
    assert len(_extract_comparison_entities("best worst CommandCode models for quota usage")) < 2


def test_empty_query_is_empty():
    assert _extract_comparison_entities("") == []


def test_duplicate_spellings_collapse():
    entities = _extract_comparison_entities(
        "comparing Inkling vs GLM-5.3 for coding agents, Inkling vs GLM 5.3"
    )
    lowered = [entity.lower().replace("-", " ") for entity in entities]
    assert len(lowered) == len(set(lowered))


def test_entity_runs_keeps_a_product_noun_tail():
    """'DeepSeek Harness' IS the product name — dropping 'Harness' sent the
    search to generic DeepSeek threads (measured on Serper, 2026-10-18)."""
    runs = _entity_runs("DeepSeek Harness dsh CLI experience")
    assert runs and " ".join(runs[0]) == "DeepSeek Harness"


def test_entity_runs_still_drops_ordinary_generic_tails():
    runs = _entity_runs("Qwen 3.8 Max best value models comparison")
    assert runs and " ".join(runs[0]) == "Qwen 3.8 Max"


# --- the channel the extraction feeds ----------------------------------------


def _plan_tasks(monkeypatch, entities, *, enabled: bool, intent="comparison"):
    from src.services.reddit_enhanced_service import RedditEnhancedService
    from src import config as reddit_config

    service = object.__new__(RedditEnhancedService)
    monkeypatch.setattr(service, "_search_with_sort", lambda *a, **k: None)
    monkeypatch.setattr(reddit_config, "REDDIT_COMPARISON_ENTITY_PAIR", enabled)
    search_plan = {
        "subreddits": ["LocalLLaMA"],
        "queries": ["GLM-5.3 Flash vs DeepSeek V4.1 Flash"],
        "keywords": [],
        "time_filter": "all",
        "intent": intent,
    }
    tasks, meta = service._build_search_tasks_v2(
        "GLM-5.3 Flash vs DeepSeek V4.1 Flash",
        "GLM-5.3 Flash vs DeepSeek V4.1 Flash",
        search_plan,
        ["LocalLLaMA"],
        anchor_terms=["glm-5.3", "v4.1"],
        comparison_entities=entities,
    )
    return [name for name, _ in tasks], meta


def test_entity_channel_is_added_when_enabled(monkeypatch):
    names, meta = _plan_tasks(
        monkeypatch, ["GLM-5.3 Flash", "DeepSeek V4.1 Flash"], enabled=True
    )
    assert "comparison_entity_pair" in names
    assert meta["comparison_entity_pair"]["query"] == "GLM-5.3 Flash DeepSeek V4.1 Flash"
    # The old channel stays: the flag adds a probe, it does not replace one.
    assert "comparison_anchor_relevance" in names


def test_entity_channel_disappears_when_flag_is_off(monkeypatch):
    names, _ = _plan_tasks(
        monkeypatch, ["GLM-5.3 Flash", "DeepSeek V4.1 Flash"], enabled=False
    )
    assert "comparison_entity_pair" not in names


def test_entity_channel_needs_a_pair(monkeypatch):
    names, _ = _plan_tasks(monkeypatch, ["GLM-5.3"], enabled=True)
    assert "comparison_entity_pair" not in names


def test_entity_channel_ignores_non_comparison_intent(monkeypatch):
    names, _ = _plan_tasks(
        monkeypatch,
        ["GLM-5.3 Flash", "DeepSeek V4.1 Flash"],
        enabled=True,
        intent="how_to",
    )
    assert "comparison_entity_pair" not in names


# --- the Google/Serper query form --------------------------------------------


def test_serper_query_uses_quoted_pair(monkeypatch):
    from src.services.reddit_enhanced_service import RedditEnhancedService
    from src import config as reddit_config

    monkeypatch.setattr(reddit_config, "REDDIT_SERPER_ENTITY_QUERY", True)
    query = RedditEnhancedService._serper_query(
        "GLM-5.3 Flash latency DeepSeek V4.1 Flash agentic coding",
        ["GLM-5.3 Flash", "DeepSeek V4.1 Flash"],
    )
    assert query == '"GLM-5.3 Flash" "DeepSeek V4.1 Flash"'


def test_serper_query_keeps_plan_query_without_a_pair(monkeypatch):
    from src.services.reddit_enhanced_service import RedditEnhancedService
    from src import config as reddit_config

    monkeypatch.setattr(reddit_config, "REDDIT_SERPER_ENTITY_QUERY", True)
    assert (
        RedditEnhancedService._serper_query("dsh-cli terminal client", ["DeepSeek"])
        == "dsh-cli terminal client"
    )
    assert (
        RedditEnhancedService._serper_query("plain query", None) == "plain query"
    )


def test_serper_query_respects_flag(monkeypatch):
    from src.services.reddit_enhanced_service import RedditEnhancedService
    from src import config as reddit_config

    monkeypatch.setattr(reddit_config, "REDDIT_SERPER_ENTITY_QUERY", False)
    assert (
        RedditEnhancedService._serper_query("plan query", ["A model", "B model"])
        == "plan query"
    )


@pytest.mark.asyncio
async def test_serper_retries_with_the_plain_query_when_quotes_return_nothing(
    monkeypatch,
):
    """An empty channel must not be silently indistinguishable from a miss."""
    import httpx
    from src.services.reddit_enhanced_service import RedditEnhancedService

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        payload = _json.loads(request.content.decode())
        calls.append(payload["q"])
        if payload["q"].startswith('"A model"'):
            return httpx.Response(200, json={"organic": []})
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "link": "https://www.reddit.com/r/test/comments/abc123/thread/",
                        "title": "A vs B",
                        "snippet": "comparison",
                    }
                ]
            },
        )

    service = object.__new__(RedditEnhancedService)
    service.base_url = "http://proxy"
    service._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service._enrich_cache = {}
    monkeypatch.setattr(
        "src.services.reddit_enhanced_service.config.SERPER_API_KEY", "test-key"
    )
    try:
        posts = await service._search_serper(
            '"A model" "B model"',
            fallback_query="A model vs B model",
        )
    finally:
        await service._client.aclose()

    assert len(calls) == 2
    assert posts and posts[0].id == "abc123"
    assert posts[0].found_by_strategy == "serp_google_discovery"
