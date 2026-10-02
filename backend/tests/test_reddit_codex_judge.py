"""Subscription-only authentication and tool-free judge completion contract."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils import reddit_codex_judge as judge


def encoded(*events):
    return "\n".join(json.dumps(e) for e in events).encode()


def test_completed_answer_and_usage_are_required():
    message = {"type": "item.completed", "item": {
        "type": "agent_message", "text": '{"ratings": []}',
    }}
    with pytest.raises(RuntimeError, match="no completed answer"):
        judge.parse_response(encoded(message))
    response = judge.parse_response(encoded(message, {
        "type": "turn.completed", "usage": {
            "input_tokens": 123, "output_tokens": 45, "cached_input_tokens": 67,
        },
    }))
    assert response.choices[0].message.content == '{"ratings": []}'
    assert response.usage.prompt_tokens == 123
    assert response.usage.completion_tokens == 45
    assert response.usage.cached_tokens == 67


@pytest.mark.parametrize("event_type", ["error", "turn.failed"])
def test_failed_turn_is_not_a_completed_judgement(event_type):
    with pytest.raises(RuntimeError, match="failed turn"):
        judge.parse_response(encoded({"type": event_type}))


@pytest.mark.parametrize("item_type", ["command_execution", "mcp_tool_call", "web_search"])
def test_tool_use_cannot_be_accepted_as_pure_rerank(item_type):
    with pytest.raises(RuntimeError, match="unexpected item"):
        judge.parse_response(encoded({
            "type": "item.started", "item": {"type": item_type},
        }))


def test_api_credentials_are_not_passed_to_subscription_process(monkeypatch):
    for key in ["OPENAI_API_KEY", "CODEX_API_KEY", "OPENROUTER_API_KEY", "CODEX_ACCESS_TOKEN", "AGENT_CONTEXT_API_TOKEN"]:
        monkeypatch.setenv(key, "test-only-placeholder")
    env = judge.subscription_environment()
    assert not any(key in env for key in [
        "OPENAI_API_KEY", "CODEX_API_KEY", "OPENROUTER_API_KEY",
        "CODEX_ACCESS_TOKEN", "AGENT_CONTEXT_API_TOKEN",
    ])


def test_command_forces_chatgpt_low_and_disables_tools():
    command = judge.judge_command()
    assert 'forced_login_method="chatgpt"' in command
    assert 'model_reasoning_effort="low"' in command
    assert 'web_search="disabled"' in command
    assert "mcp_servers={}" in command
    assert "--ignore-user-config" in command
    assert "--ephemeral" in command
    assert command[-1] == "-"
    assert command[command.index("--model") + 1] == "gpt-6.1-sol"
    for name in ["shell_tool", "unified_exec", "apps", "plugins", "multi_agent"]:
        assert command[command.index(name) - 1] == "--disable"


@pytest.mark.asyncio
async def test_nonzero_exit_does_not_leak_process_diagnostics(monkeypatch):
    process = SimpleNamespace(
        returncode=1,
        communicate=AsyncMock(return_value=(b"", b"private diagnostic placeholder")),
    )
    monkeypatch.setattr(judge.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(RuntimeError, match=r"^Codex judge failed \(exit 1\)$"):
        await judge.RedditCodexJudgeClient().chat_completions_create(
            messages=[{"role": "user", "content": "source text"}],
        )
    process.communicate.assert_awaited_once_with(b"source text")
