"""Regression checks for the DeepSeek Harness engine adapter.

No live `dsh` call happens here: the NDJSON stream, the subprocess command and
the child environment are asserted directly, so a regression is caught even
when the CLI is absent (CI).
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import dsh_client
from src.services.dsh_client import (
    DshHeadlessLLMClient,
    DshLLMError,
    DshResponse,
    parse_events,
)


def run_stream(*events: dict) -> bytes:
    return ("\n".join(json.dumps(e) for e in events) + "\n").encode()


COMPLETED_STREAM = run_stream(
    {"type": "session", "sessionId": "session-1", "cwd": "/tmp"},
    {"type": "status", "phase": "turn_start", "turn": 1},
    {"type": "status", "phase": "step_start", "turn": 1, "step": 1},
    {"type": "text", "text": '{"ratings":[]}'},
    {
        "type": "status",
        "phase": "step_end",
        "turn": 1,
        "step": 1,
        "usage": {
            "inputTokens": 1317,
            "outputTokens": 42,
            "totalTokens": 5415,
            "cacheReadTokens": 4096,
        },
    },
    {"type": "status", "phase": "turn_end", "turn": 1, "reason": {"kind": "completed"}},
    {"type": "final", "text": '{"ratings":[]}'},
)


def test_parse_events_returns_the_final_message():
    response = parse_events(COMPLETED_STREAM, "judge")
    assert response.choices[0].message.content == '{"ratings":[]}'
    assert response.choices[0].finish_reason == "stop"
    assert response.model == "judge"


def test_parse_events_exposes_usage_tokens():
    response = parse_events(COMPLETED_STREAM, "judge")
    assert response.usage.prompt_tokens == 1317
    assert response.usage.completion_tokens == 42
    assert response.usage.cached_tokens == 4096


def test_parse_events_maps_output_limit_to_length():
    stream = run_stream(
        {"type": "status", "phase": "turn_end", "turn": 1, "reason": {"kind": "length"}},
        {"type": "final", "text": '{"ratings":[{"id":0,'},
    )
    assert parse_events(stream, "judge").choices[0].finish_reason == "length"


def test_parse_events_without_final_message_fails():
    stream = run_stream({"type": "status", "phase": "turn_start", "turn": 1})
    with pytest.raises(DshLLMError):
        parse_events(stream, "judge")


def test_parse_events_surfaces_a_failed_turn():
    stream = run_stream({"type": "error", "message": "quota"})
    with pytest.raises(DshLLMError):
        parse_events(stream, "judge")


def test_ambient_harness_state_is_not_inherited(monkeypatch):
    """A nested call must not adopt the caller's interactive profile.

    The harness exports DSH_PROFILE/DSH_SESSION_ID into every process it
    starts; inheriting DSH_PROFILE=dsh-tui made the adapter boot the TUI
    profile and hang.
    """
    monkeypatch.setenv("DSH_PROFILE", "dsh-tui")
    monkeypatch.setenv("DSH_PROFILE_DIR", "/home/ubuntu/.dsh/profiles/dsh-tui")
    monkeypatch.setenv("DSH_SESSION_ID", "session-abc")
    monkeypatch.setenv("DSH_HOME", "/home/ubuntu/.dsh")

    env = dsh_client._subscription_environment()

    assert env["DSH_PROFILE"] == dsh_client.DSH_PROFILE == "headless"
    assert "DSH_SESSION_ID" not in env
    assert "DSH_PROFILE_DIR" not in env
    assert env["DSH_HOME"] == "/home/ubuntu/.dsh"


def test_provider_keys_are_not_passed_to_the_child(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    monkeypatch.setenv("REDDIT_SEARCH_API_TOKEN", "secret")
    env = dsh_client._subscription_environment()
    assert "OPENROUTER_API_KEY" not in env
    assert "REDDIT_SEARCH_API_TOKEN" not in env


def test_command_passes_tool_free_patch_and_effort_overlay(monkeypatch, tmp_path):
    monkeypatch.setattr(dsh_client, "DSH_PATCH_PATH", "/repo/reddit-llm.patch.yml")
    monkeypatch.setattr(dsh_client, "_OVERLAY_DIR", tmp_path)
    command = dsh_client.dsh_command(reasoning_effort="high")
    assert command[:3] == [dsh_client.DSH_BIN, "--profile", "headless"]
    patches = [command[i + 1] for i, part in enumerate(command) if part == "--patch"]
    assert patches == ["/repo/reddit-llm.patch.yml", str(tmp_path / "effort-high.yml")]
    assert command[-2:] == ["--json", "-"]


def test_command_without_effort_keeps_the_single_patch(monkeypatch, tmp_path):
    monkeypatch.setattr(dsh_client, "DSH_PATCH_PATH", "/repo/reddit-llm.patch.yml")
    monkeypatch.setattr(dsh_client, "_OVERLAY_DIR", tmp_path)
    command = dsh_client.dsh_command()
    assert command.count("--patch") == 1


def test_synthesis_tier_gets_high_reasoning_effort(monkeypatch):
    from src import config

    monkeypatch.setattr(config, "MODEL_SYNTHESIS", "google/gemini-3-flash-preview")
    monkeypatch.setattr(config, "MODEL_ANALYSIS", "google/gemini-3.1-flash-lite")
    assert dsh_client.set_reasoning_effort_for_model(config.MODEL_SYNTHESIS) == "high"
    assert dsh_client.set_reasoning_effort_for_model(config.MODEL_ANALYSIS) == "low"


def test_effort_override_pins_every_role(monkeypatch):
    """The A/B harness measures a cheaper effort without touching the code."""
    from src import config

    monkeypatch.setenv("REDDIT_DSH_EFFORT_OVERRIDE", "off")
    assert dsh_client.set_reasoning_effort_for_model(config.MODEL_SYNTHESIS) == "off"
    assert dsh_client.set_reasoning_effort_for_model(config.MODEL_ANALYSIS) == "off"

    monkeypatch.setenv("REDDIT_DSH_EFFORT_OVERRIDE", "nonsense")
    assert dsh_client.set_reasoning_effort_for_model(config.MODEL_ANALYSIS) == "low"


@pytest.mark.asyncio
async def test_client_accepts_openrouter_style_kwargs(monkeypatch, tmp_path):
    """temperature/max_tokens are accepted and ignored, never forwarded."""
    monkeypatch.setattr(dsh_client, "_OVERLAY_DIR", tmp_path)
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self, payload):
            captured["payload"] = payload
            return COMPLETED_STREAM, b""

    async def fake_exec(*command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return FakeProc()

    monkeypatch.setattr(dsh_client.asyncio, "create_subprocess_exec", fake_exec)
    client = DshHeadlessLLMClient(timeout_s=5)
    response = await client.chat_completions_create(
        model="judge",
        messages=[{"role": "user", "content": "rate these"}],
        temperature=0.0,
        max_tokens=3072,
    )
    assert response.choices[0].message.content == '{"ratings":[]}'
    assert not any("3072" in str(part) for part in captured["command"])
    assert captured["payload"] == b"rate these"
    # The neutral working directory keeps repository context out of the prompt.
    assert captured["cwd"] == "/tmp"


@pytest.mark.asyncio
async def test_empty_prompt_is_rejected_before_spawning():
    client = DshHeadlessLLMClient(timeout_s=5)
    with pytest.raises(DshLLMError):
        await client.chat_completions_create(model="judge", messages=[])


def test_engine_switch_returns_dsh_client(monkeypatch):
    from src import config

    monkeypatch.setattr(config, "REDDIT_LLM_BACKEND", "dsh")
    assert isinstance(dsh_client.get_reddit_llm_client(), DshHeadlessLLMClient)


def test_engine_switch_can_return_the_openrouter_client(monkeypatch):
    from src import config
    from src.services import vertex_llm_client

    sentinel = SimpleNamespace(name="openrouter")
    monkeypatch.setattr(config, "REDDIT_LLM_BACKEND", "gemini")
    monkeypatch.setattr(vertex_llm_client, "get_vertex_llm_client", lambda: sentinel)
    assert dsh_client.get_reddit_llm_client() is sentinel


def test_response_shape_matches_the_openrouter_surface():
    response = DshResponse("text", "model", "stop", {"inputTokens": 1})
    assert response.choices[0].message.content == "text"
    assert response.choices[0].finish_reason == "stop"
    assert response.usage.prompt_tokens == 1
