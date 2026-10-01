"""Model comparison must preserve Scout's tool contract and evidence reads."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("scout_benchmark_test", ROOT / "backend/scripts/benchmark_scout_models.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


@pytest.mark.parametrize("status, expected", [("completed", 1), ("failed", 0)])
def test_count_only_successful_source_reads(status, expected):
    event = {"type": "item.completed", "item": {
        "type": "mcp_tool_call", "tool": "scout", "status": status,
        "arguments": {"command": "show", "source_keys": ["video_hub:1"]},
        "result": {"content": [{"type": "text", "text": json.dumps([
            {"source_key": "video_hub:1", "content": "Primary source"}
        ])}]},
    }}
    report = bench.evaluate_events("luna", [event], "See video_hub:1")
    assert report["read_sources"] == expected
    assert bool(report["citations_without_captured_show"]) == (expected == 0)


def test_plain_show_is_evidence_but_comment_is_not_source_quote():
    text = ("=== video_hub:1 [2026-01-01] @video_hub_internal ===\n"
            "video: https://www.youtube.com/watch?v=abc&t=5s\n"
            "Original source words\n--- author comments (0) ---\n"
            "--- community comments (1) ---\nA comment, not the expert's words\n")
    sources = bench.unpack_sources(text)
    assert len(sources) == 1
    assert sources[0]["source_key"] == "video_hub:1"
    assert "Original source" in sources[0]["content"]
    assert "A comment" not in sources[0]["content"]


def test_tool_error_cannot_count_as_read_source():
    event = {"type": "item.completed", "item": {
        "type": "mcp_tool_call", "tool": "scout", "status": "completed",
        "arguments": {"command": "show"},
        "result": {"isError": True, "content": [{"type": "text", "text": json.dumps([
            {"source_key": "video_hub:1", "content": "Partial error payload"}
        ])}]},
    }}
    report = bench.evaluate_events("sol", [event], "See video_hub:1")
    assert report["read_sources"] == 0
    assert report["calls"][0]["output_error"]


def test_unfinished_turn_is_failed_evaluation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["benchmark", "--engine", "sol", "--case", "old_craft"])
    monkeypatch.setattr(bench, "run", lambda *args: {
        "exit": 0, "run_completed": False, "answer": "Intermediate narration",
    })
    assert bench.main() == 1


def test_timeout_returns_failure_and_keeps_live_output():
    result = bench.run_process([
        sys.executable, "-c", "import time; print('started', flush=True); time.sleep(5)",
    ], dict(os.environ), timeout=0.2)
    assert result.returncode == 124
    assert "started" in result.stdout
    assert "scout-eval-timeout" in result.stderr


@pytest.mark.parametrize("engine,model,effort", [
    ("luna", "gpt-6-luna", "max"), ("sol", "gpt-6.1-sol", "low"),
])
def test_codex_has_same_scout_tool_and_no_shell(engine, model, effort):
    cmd = bench.codex_command(engine)
    assert cmd[cmd.index("--model") + 1] == model
    assert f'model_reasoning_effort="{effort}"' in cmd
    assert 'mcp_servers.expert_scout.enabled_tools=["scout"]' in cmd
    assert ["--disable", "shell_tool"] == cmd[cmd.index("shell_tool") - 1:cmd.index("shell_tool") + 1]
    assert "--ignore-user-config" in cmd and "--ephemeral" in cmd


def test_runtime_fast_keeps_low_reasoning_and_is_scoped_to_invocation():
    cmd=bench.codex_command('sol',fast=True)
    assert 'service_tier="fast"' in cmd and 'features.fast_mode=true' in cmd
    assert 'model_reasoning_effort="low"' in cmd
    assert '--strict-config' in cmd
    assert not any('service_tier' in arg for arg in bench.codex_command('sol'))


@pytest.mark.skipif(not shutil.which("bun"), reason="Bun is required by the existing Scout plugin")
def test_mcp_reuses_schema_and_rejects_invalid_calls_without_corpus_access():
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "scout", "arguments": {"command": "search", "query": "x", "limit": 41}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "scout", "arguments": {"command": "bash"}}},
    ]
    proc = subprocess.run(["bun", "run", str(ROOT / "scripts/expert_scout_mcp.ts")],
                          input="\n".join(map(json.dumps, requests)) + "\n", text=True,
                          capture_output=True, timeout=10, check=True)
    results = [json.loads(line)["result"] for line in proc.stdout.splitlines()]
    tool = results[1]["tools"][0]
    assert tool["name"] == "scout"
    assert tool["inputSchema"]["properties"]["command"]["enum"] == ["experts", "videos", "search", "digest", "show"]
    assert results[2]["isError"] and results[3]["isError"]


def test_mimo_uses_drift_connection_but_scout_agent(monkeypatch):
    commands = []
    events = [
        {'type': 'text', 'part': {'text': 'Final answer', 'messageID': 'answer'}},
        {'type': 'step_finish', 'part': {'reason': 'stop'}},
    ]

    def run_process(command, env, timeout):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '\n'.join(map(json.dumps, events)), '')

    monkeypatch.setattr(bench, 'run_process', run_process)
    result = bench.run('mimo', 'test', 30, question='Test question')
    command = commands[0]
    assert command[0] == bench.OPENCODE_BIN
    assert command[command.index('--attach') + 1] == bench.OPENCODE_URL
    assert command[command.index('--model') + 1] == bench.OPENCODE_MODEL
    assert command[command.index('--agent') + 1] == 'expert-scout'
    assert command[command.index('--dir') + 1] == str(ROOT)
    assert command[-1] == 'Test question'
    assert result['answer'] == 'Final answer'
    assert result['run_completed'] is True


def test_codex_finds_bun_in_nonlogin_ssh_environment(monkeypatch, tmp_path):
    from src.utils import scout_codex
    bun = tmp_path / '.bun/bin/bun'
    bun.parent.mkdir(parents=True)
    bun.write_text('#!/bin/sh\nexit 0\n')
    bun.chmod(0o755)
    monkeypatch.setattr(scout_codex.shutil, 'which', lambda name: None)
    monkeypatch.setattr(scout_codex.Path, 'home', lambda: tmp_path)
    command = scout_codex.codex_command('sol')
    assert 'mcp_servers.expert_scout.command=' + json.dumps(str(bun)) in command


def test_missing_bun_fails_before_starting_model(monkeypatch, tmp_path):
    from src.utils import scout_codex
    monkeypatch.setattr(scout_codex.shutil, 'which', lambda name: None)
    monkeypatch.setattr(scout_codex.Path, 'home', lambda: tmp_path)
    with pytest.raises(RuntimeError, match='Scout requires Bun'):
        scout_codex.codex_command('sol')
