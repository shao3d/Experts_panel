"""Contract tests for Harvester's Hermes pre_tool_call guard."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


OVERLAY_HOOK = (
    Path(__file__).resolve().parents[2]
    / "hermes-data"
    / "hooks"
    / "research_terminal_guard.py"
)
CONTAINER_HOOK = Path("/opt/data/hooks/research_terminal_guard.py")
HOOK = OVERLAY_HOOK if OVERLAY_HOOK.exists() else CONTAINER_HOOK
OVERLAY_CONFIG = Path(__file__).resolve().parents[2] / "hermes-data" / "config.yaml"
CONTAINER_CONFIG = Path("/opt/data/config.yaml")
CONFIG = OVERLAY_CONFIG if OVERLAY_CONFIG.exists() else CONTAINER_CONFIG


def _run_hook(tool_name: str, tool_input: dict[str, str]) -> dict[str, str] | None:
    payload = {
        "hook_event_name": "pre_tool_call",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": "test-session",
        "cwd": "/srv/searxng-docker/jobs/job-id",
        "extra": {},
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def test_guard_allows_searcharvester_wrapper_command():
    result = _run_hook(
        "terminal",
        {"command": 'searcharvester-search --query "Cloud Run pricing 2026" --max-results 5'},
    )

    assert result is None


def test_guard_allows_searcharvester_subcommand_wrapper():
    result = _run_hook(
        "terminal",
        {"command": 'searcharvester search --query "Cloud Run pricing 2026" --max-results 5'},
    )

    assert result is None


def test_guard_allows_usr_local_bin_wrappers():
    result = _run_hook(
        "terminal",
        {"command": '/usr/local/bin/searcharvester-extract --url "https://cloud.google.com/run/pricing"'},
    )

    assert result is None


def test_guard_allows_script_alias_command():
    result = _run_hook(
        "terminal",
        {"command": 'search.py --query "SearXNG Docker setup" --max-results 3'},
    )

    assert result is None


def test_guard_allows_searcharvester_absolute_script_command():
    result = _run_hook(
        "terminal",
        {
            "command": (
                "python3 /opt/data/skills/searcharvester-extract/scripts/extract.py "
                "--url https://cloud.google.com/run/pricing"
            )
        },
    )

    assert result is None


def test_guard_blocks_relative_python_script_lookup():
    result = _run_hook(
        "terminal",
        {"command": 'python3 search.py --query "SearXNG Docker setup" --max-results 3'},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "research command contract" in result["message"]


def test_guard_blocks_search_without_query_flag():
    result = _run_hook(
        "terminal",
        {"command": 'searcharvester-search "SearXNG Docker setup" --max-results 3'},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "--query" in result["message"]


def test_guard_blocks_extract_with_extra_positional_url():
    result = _run_hook(
        "terminal",
        {
            "command": (
                'searcharvester-extract --url "https://docs.cloud.google.com/run/docs/configuring/task-timeout" '
                '"https://cloud.google.com/run/pricing"'
            )
        },
    )

    assert result is not None
    assert result["action"] == "block"
    assert "Unexpected positional argument" in result["message"]


def test_guard_blocks_chained_extract_commands():
    result = _run_hook(
        "terminal",
        {
            "command": (
                'searcharvester-extract --url "https://cloud.google.com/run/pricing" && '
                'searcharvester-extract --url "https://docs.railway.com/"'
            )
        },
    )

    assert result is not None
    assert result["action"] == "block"
    assert "one Harvester search/extract command" in result["message"]


def test_guard_blocks_imagined_google_search_tool():
    result = _run_hook("google_search", {"q": "Cloud Run pricing"})

    assert result is not None
    assert result["action"] == "block"
    assert "searcharvester-search" in result["message"]


def test_guard_blocks_internal_service_probe():
    result = _run_hook(
        "terminal",
        {"command": 'curl -G "http://searxng:8080/search" --data-urlencode "q=test"'},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "internal services" in result["message"]


def test_guard_blocks_container_introspection():
    result = _run_hook(
        "terminal",
        {"command": 'python3 -c "import os; print(os.listdir(\"/usr/local/bin\"))"'},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "introspect" in result["message"]


def test_guard_allows_report_size_check():
    result = _run_hook("terminal", {"command": "wc -c ./report.md"})

    assert result is None


def test_guard_allows_safe_extract_reader():
    result = _run_hook(
        "terminal",
        {"command": 'grep -n "pricing" ./extracts/cloud-run.md'},
    )

    assert result is None


def test_guard_allows_safe_extract_reader_without_dot_prefix():
    result = _run_hook(
        "terminal",
        {"command": "head -n 200 extracts/cloud-run.md"},
    )

    assert result is None


def test_guard_blocks_unknown_terminal_command_by_default():
    result = _run_hook(
        "terminal",
        {"command": 'python3 /srv/searxng-docker/search.py --query "SearXNG Docker setup"'},
    )

    assert result is not None
    assert result["action"] == "block"
    assert "research command contract" in result["message"]


def test_guard_blocks_destructive_terminal_command():
    result = _run_hook("terminal", {"command": "rm -rf ./extracts"})

    assert result is not None
    assert result["action"] == "block"
    assert "research command contract" in result["message"]


def test_entrypoint_exposes_research_wrappers_to_usr_local_bin():
    entrypoint = (
        Path(__file__).resolve().parents[1]
        / "docker"
        / "entrypoint-adapter.sh"
    ).read_text(encoding="utf-8")

    assert "/usr/local/bin/searcharvester-search" in entrypoint
    assert "/usr/local/bin/searcharvester-extract" in entrypoint
    assert "/usr/local/bin/search.py" in entrypoint
    assert "/usr/local/bin/extract.py" in entrypoint


def test_config_auto_approves_subagents_only_with_guard():
    config = CONFIG.read_text(encoding="utf-8")

    assert "python3 /opt/data/hooks/research_terminal_guard.py" in config
    assert "delegation:" in config
    assert "  subagent_auto_approve: true" in config
