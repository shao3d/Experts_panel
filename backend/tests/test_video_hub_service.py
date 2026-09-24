#!/usr/bin/env python3
"""VideoHubService: honest failure reporting and retry behaviour.

Map failures (LLM errors, broken score responses) must NOT masquerade as the
"no relevant segments" fallback: they return a localized temporary-unavailable
answer after retries. Synthesis failures retry too and then raise (the
orchestrator shows the error event). An all-LOW verdict stays the only path to
the empty-result fallback.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class FakeLLM:
    """Async fake of the LLM client: queued map replies + synthesis replies.

    Each reply is either an Exception to raise or a response-content string.
    When a queue is exhausted its last item repeats. Map vs synthesis calls are
    distinguished by the "Video Content Scorer" marker in the prompt.
    """

    def __init__(self, map_replies, synth_replies=None):
        self.map_replies = list(map_replies)
        self.synth_replies = list(synth_replies or ["synth ok"])
        self.map_calls = 0
        self.synth_calls = 0
        self.map_prompts = []

    async def chat_completions_create(self, *, model=None, messages=None, **kwargs):
        prompt = " ".join(m.get("content", "") for m in (messages or []))
        is_map = "Video Content Scorer" in prompt
        if is_map:
            self.map_calls += 1
            self.map_prompts.append(prompt)
            queue = self.map_replies
        else:
            self.synth_calls += 1
            queue = self.synth_replies
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(reply):
            reply = reply(prompt)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
        )


def scores_json(*pairs) -> str:
    return json.dumps(
        {"scores": [{"id": i, "relevance": r} for i, r in pairs]},
        ensure_ascii=False,
    )


def make_post(mid: int = 111, topic: str = "intro") -> SimpleNamespace:
    return SimpleNamespace(
        telegram_message_id=mid,
        message_text="TITLE: T1\nSUMMARY: S1\n---\nCONTENT:\nc1",
        media_metadata=json.dumps({"topic_id": topic, "timestamp_seconds": 10}),
    )


@pytest.fixture()
def vhs(monkeypatch):
    import src.services.video_hub_service as module

    class StubValidator:
        async def process(self, answer, query, expert_id):
            return {"answer": answer}

    monkeypatch.setattr(module, "LanguageValidationService", StubValidator)
    return module


def build_service(vhs, llm, **kwargs):
    return vhs.VideoHubService(
        llm_client=llm, map_max_attempts=3, retry_wait_min=0, **kwargs
    )


RU_QUERY = "как экономить кредиты в Seedance"
EN_QUERY = "how to save credits with Seedance"


async def test_map_failure_returns_localized_unavailable_ru(vhs):
    llm = FakeLLM([RuntimeError("llm down")])
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post()])

    assert llm.map_calls == 3  # three knocks
    assert "недоступен" in result["answer"]
    assert "не найдено" not in result["answer"]
    assert result["confidence"] == "LOW"
    assert result["main_sources"] == []


async def test_map_failure_returns_localized_unavailable_en(vhs):
    llm = FakeLLM([RuntimeError("llm down")])
    svc = build_service(vhs, llm)

    result = await svc.process(EN_QUERY, [make_post()])

    assert "temporarily unavailable" in result["answer"]
    assert "does not contain" not in result["answer"]


async def test_map_retry_recovers_after_transient_failures(vhs):
    llm = FakeLLM(
        [RuntimeError("boom"), ValueError("bad json"), scores_json((111, "HIGH"))],
        ["the expert answer"],
    )
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post()])

    assert llm.map_calls == 3
    assert result["answer"] == "the expert answer"
    assert result["main_sources"] == [111]
    assert result["confidence"] == "HIGH"


async def test_all_low_scores_is_honest_not_found(vhs):
    llm = FakeLLM([scores_json((111, "LOW"))])
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post()])

    assert llm.map_calls == 1  # nothing to retry: scorer worked fine
    assert llm.synth_calls == 0
    assert "не найдено" in result["answer"]
    assert result["confidence"] == "LOW"


async def test_all_low_scores_not_found_english_query(vhs):
    llm = FakeLLM([scores_json((111, "LOW"))])
    svc = build_service(vhs, llm)

    result = await svc.process(EN_QUERY, [make_post()])

    assert "does not contain" in result["answer"]


async def test_garbage_scores_json_retried_then_unavailable(vhs):
    llm = FakeLLM(["this is not json {"])
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post()])

    assert llm.map_calls == 3
    assert "недоступен" in result["answer"]
    assert "не найдено" not in result["answer"]


async def test_phantom_only_scores_count_as_broken_response(vhs):
    llm = FakeLLM([scores_json((999999, "HIGH"))])
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post()])

    assert llm.map_calls == 3  # unusable scores retried like a crash
    assert "недоступен" in result["answer"]


async def test_synthesis_retry_recovers(vhs):
    llm = FakeLLM([scores_json((111, "HIGH"))], [RuntimeError("flaky"), "recovered answer"])
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post()])

    assert llm.synth_calls == 2
    assert result["answer"] == "recovered answer"


async def test_synthesis_failure_raises_after_retries(vhs):
    llm = FakeLLM([scores_json((111, "HIGH"))], [RuntimeError("synth down")])
    svc = build_service(vhs, llm)

    with pytest.raises(Exception):
        await svc.process(RU_QUERY, [make_post()])

    assert llm.synth_calls == 3


async def test_happy_path_cites_high_segments(vhs):
    llm = FakeLLM([scores_json((111, "HIGH"), (222, "LOW"))], ["twin answer"])
    svc = build_service(vhs, llm)

    result = await svc.process(
        RU_QUERY, [make_post(111, topic="intro"), make_post(222, topic="other")]
    )

    assert result["answer"] == "twin answer"
    assert result["main_sources"] == [111]
    assert result["confidence"] == "HIGH"
    assert result["posts_analyzed"] == 2


def _ids_in_prompt(prompt: str) -> list[int]:
    """Segment ids from the prompt's segment list (not the template examples)."""
    return [int(x) for x in re.findall(r'"id": (\d+),\s*"topic_id"', prompt)]


async def test_map_scores_in_chunks_of_configured_size(vhs):
    posts = [make_post(1000 + i, topic=f"t{i}") for i in range(120)]

    def score_whats_in_the_prompt(prompt):
        return scores_json(*[(mid, "HIGH") for mid in _ids_in_prompt(prompt)])

    llm = FakeLLM([score_whats_in_the_prompt])
    svc = build_service(vhs, llm, map_chunk_size=30)

    result = await svc.process(RU_QUERY, posts)

    assert llm.map_calls == 4  # 120 segments -> 4 prompts of <=30
    assert all(len(_ids_in_prompt(p)) <= 30 for p in llm.map_prompts)
    assert sorted(result["main_sources"]) == [1000 + i for i in range(120)]
    assert result["confidence"] == "HIGH"


async def test_one_failing_chunk_fails_whole_map_honestly(vhs):
    # A chunk that never scores must fail the whole Map: partial results would
    # silently drop that chunk's segments instead of admitting the problem.
    def score_whats_in_the_prompt(prompt):
        return scores_json(*[(mid, "HIGH") for mid in _ids_in_prompt(prompt)])

    llm = FakeLLM([score_whats_in_the_prompt, RuntimeError("chunk down")])
    svc = build_service(vhs, llm, map_chunk_size=1)

    result = await svc.process(RU_QUERY, [make_post(1), make_post(2, topic="other")])

    assert llm.map_calls == 4  # 1 ok call + 3 knocks on the broken chunk
    assert "недоступен" in result["answer"]
    assert "не найдено" not in result["answer"]


async def test_chunk_merge_keeps_every_scored_segment(vhs):
    posts = [make_post(1), make_post(2, topic="other"), make_post(3, topic="third")]

    def mixed(prompt):
        ids = _ids_in_prompt(prompt)
        return scores_json(*[(i, "HIGH" if i == 3 else "LOW") for i in ids])

    llm = FakeLLM([mixed])
    svc = build_service(vhs, llm, map_chunk_size=2)

    result = await svc.process(RU_QUERY, posts)

    assert llm.map_calls == 2  # 3 segments -> chunks of 2 + 1
    assert result["main_sources"] == [3]
    assert result["confidence"] == "HIGH"


async def test_topic_sibling_is_pulled_as_narrative_bridge(vhs):
    # A LOW sibling inside the winning topic comes along as a MEDIUM bridge
    # and is therefore cited too (thread expansion design).
    llm = FakeLLM([scores_json((111, "HIGH"), (222, "LOW"))], ["twin answer"])
    svc = build_service(vhs, llm)

    result = await svc.process(RU_QUERY, [make_post(111), make_post(222)])

    assert sorted(result["main_sources"]) == [111, 222]
