#!/usr/bin/env python3
"""BDD dogfood tests for the local experts_panel_researcher workflow."""

import json
import re
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

CLAUDE_AGENT_PATH = REPO_ROOT / ".claude" / "agents" / "experts_panel_researcher.md"
CODEX_AGENT_PATH = REPO_ROOT / ".codex" / "agents" / "experts_panel_researcher.toml"
SPEC_PATH = REPO_ROOT / "docs" / "architecture" / "agent-context-api.md"
CLI_PATH = REPO_ROOT / "backend" / "src" / "cli" / "agent_context.py"
DOGFOOD_SAMPLE_PATH = (
    REPO_ROOT
    / "backend"
    / "tests"
    / "fixtures"
    / "experts_panel_researcher_source_bundle_sample.json"
)

SIGNALS_FRAME_SECTIONS = [
    "Query and selection",
    "Source-backed signals",
    "Expert positions",
    "Convergence / divergence",
    "Practical application",
    "Limits and missing evidence",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _codex_instructions() -> str:
    with CODEX_AGENT_PATH.open("rb") as handle:
        return tomllib.load(handle)["developer_instructions"]


def _sample_payload() -> dict:
    return json.loads(_read(DOGFOOD_SAMPLE_PATH))


def _agent_instructions() -> str:
    return "\n".join([_read(CLAUDE_AGENT_PATH), _codex_instructions()])


def test_dogfood_sample_exists_and_matches_source_bundle_shape():
    payload = _sample_payload()

    assert payload["mode"] == "source_bundle"
    assert payload["query"]
    assert payload["selection_used"]["expert_scope"] == "custom"
    assert payload["selection_used"]["expert_filter"] == ["refat", "akimov"]
    assert payload["selection_used"]["include_reddit"] is False
    assert payload["selection_used"]["include_main_source_comments"] is True
    assert payload["selection_used"]["include_drift_comment_groups"] is False
    assert payload["selection_used"]["synthesis_level"] == "none"
    assert len(payload["experts"]) == 2


def test_dogfood_sample_supports_every_signals_frame_section():
    payload = _sample_payload()
    experts = {expert["expert_id"]: expert for expert in payload["experts"]}

    assert payload["query"]  # Query and selection
    assert payload["selection_used"]["expert_filter"] == ["refat", "akimov"]

    assert all(expert["selected_sources_count"] > 0 for expert in experts.values())
    assert all(expert["main_sources"] for expert in experts.values())

    all_sources = [
        source
        for expert in experts.values()
        for source in expert["main_sources"]
    ]
    assert all(source["source_role"] == "main" for source in all_sources)
    assert all(source["relevance"] in {"HIGH", "MEDIUM"} for source in all_sources)
    assert any(source["linked_context"] for source in all_sources)
    assert any(source["external_links"] for source in all_sources)
    assert all(
        link["fetch_status"] == "not_fetched"
        for source in all_sources
        for link in source["external_links"]
    )
    assert any(
        source["comments"]["author_comments"]
        or source["comments"]["community_comments"]
        for source in all_sources
    )

    refat_text = json.dumps(experts["refat"], ensure_ascii=False).lower()
    akimov_text = json.dumps(experts["akimov"], ensure_ascii=False).lower()
    assert "sales" in refat_text
    assert "sales" in akimov_text
    assert "gtm" in refat_text
    assert "operations" in akimov_text

    assert payload["warnings"]
    assert "reduce_answer_synthesis" in payload["pipeline_skipped"]
    assert "cross_expert_meta_synthesis" in payload["pipeline_skipped"]


def test_agents_treat_cli_json_as_synthesis_input_not_final_answer():
    instructions = _agent_instructions()
    normalized = _normalize(instructions)

    assert "--json" in instructions
    assert "json is input for synthesis" in normalized
    assert "do not return raw json as the final answer unless requested" in normalized
    assert "compact signals frame" in normalized
    for section in SIGNALS_FRAME_SECTIONS:
        assert section in instructions


def test_agents_have_actionable_readiness_failure_guidance():
    normalized = _normalize(_agent_instructions())

    assert "missing agent_context_api_token" in normalized
    assert "production token" in normalized
    assert "invalid agent context token" in normalized
    assert "nameresolutionerror" in normalized
    assert "fly endpoint" in normalized
    assert "unreachable local backend" in normalized
    assert "agent context api endpoint is unreachable" in normalized
    assert "video_hub" in normalized
    assert "501" in normalized
    assert "tell the parent what setup/action is needed" in normalized


def test_real_subagent_calls_pin_fly_without_relying_on_local_default():
    cli_source = _read(CLI_PATH)
    dogfood_text = "\n".join(
        [
            _agent_instructions(),
            _read(SPEC_PATH),
            _read(DOGFOOD_SAMPLE_PATH),
        ]
    )

    assert 'DEFAULT_AGENT_CONTEXT_API_URL = "http://localhost:8000/api/v1/agent/context"' in cli_source
    assert "http://localhost:8000/api/v1/agent/context" in dogfood_text
    assert "https://experts-panel.fly.dev/api/v1/agent/context" in _agent_instructions()
    assert "--api-url https://experts-panel.fly.dev/api/v1/agent/context" in _agent_instructions()
    assert "do not rely on the cli default" in _normalize(_agent_instructions())
    assert "localhost only when" in _normalize(_agent_instructions())
    assert "https://experts-panel.fly.dev" not in _read(DOGFOOD_SAMPLE_PATH)


def test_spec_records_and10_local_dogfood_contract():
    spec = _read(SPEC_PATH)
    normalized = _normalize(spec)

    assert "AND-10 local dogfood for `experts_panel_researcher`" in spec
    assert "Local Dogfood" in spec
    assert "experts_panel_researcher_source_bundle_sample.json" in spec
    assert "manual smoke" in normalized
    assert "local backend" in normalized
    for section in SIGNALS_FRAME_SECTIONS:
        assert section in spec
