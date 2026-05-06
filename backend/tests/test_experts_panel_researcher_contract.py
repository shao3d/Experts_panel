#!/usr/bin/env python3
"""BDD contract tests for the repo-local experts_panel_researcher subagent."""

import re
import subprocess
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


CLAUDE_AGENT_PATH = REPO_ROOT / ".claude" / "agents" / "experts_panel_researcher.md"
CODEX_AGENT_PATH = REPO_ROOT / ".codex" / "agents" / "experts_panel_researcher.toml"
SPEC_PATH = REPO_ROOT / "docs" / "architecture" / "agent-context-api.md"

SIGNALS_FRAME_SECTIONS = [
    "Query and selection",
    "Source-backed signals",
    "Expert positions",
    "Convergence / divergence",
    "Practical application",
    "Limits and missing evidence",
]

FORBIDDEN_PROOF_FRAME_TERMS = [
    "facts/assumptions/risks/unknowns",
    "facts / assumptions / risks / unknowns",
    "доказано / предположение / риск / unknown",
]

SECRET_LITERALS = [
    "acceptance-token",
    "secret-token",
    "super-secret-token",
    "valid-agent-token",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _codex_agent_config() -> dict:
    with CODEX_AGENT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def test_contract_files_exist_for_claude_and_codex():
    assert CLAUDE_AGENT_PATH.exists()
    assert CODEX_AGENT_PATH.exists()


def test_contract_files_are_not_git_ignored():
    for path in [CLAUDE_AGENT_PATH, CODEX_AGENT_PATH]:
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "-q",
                str(path.relative_to(REPO_ROOT)),
            ],
            cwd=REPO_ROOT,
            check=False,
        )

        assert result.returncode == 1


def test_claude_agent_is_read_only_and_uses_safe_cli_boundary():
    content = _read(CLAUDE_AGENT_PATH)
    frontmatter = content.split("---", 2)[1]

    assert "name: experts_panel_researcher" in frontmatter
    assert "tools:" in frontmatter
    assert "Read" in frontmatter
    assert "Bash" in frontmatter
    assert "Write" not in frontmatter
    assert "Edit" not in frontmatter

    normalized = _normalize(content)
    assert "src.cli.agent_context" in content
    assert "expert_digest" in content
    assert "--response-mode expert_digest" in content
    assert "source_bundle" in content
    assert "explicit" in normalized
    assert "do not call /api/v1/query" in normalized
    assert "do not call admin" in normalized
    assert "do not edit files" in normalized


def test_codex_agent_is_read_only_and_uses_safe_cli_boundary():
    config = _codex_agent_config()
    instructions = config["developer_instructions"]
    normalized = _normalize(instructions)

    assert config["name"] == "experts_panel_researcher"
    assert config["model"] == "gpt-5.5"
    assert config["model_reasoning_effort"] == "medium"
    assert config["sandbox_mode"] == "read-only"
    assert "src.cli.agent_context" in instructions
    assert "expert_digest" in instructions
    assert "--response-mode expert_digest" in instructions
    assert "source_bundle" in instructions
    assert "explicit" in normalized
    assert "do not call /api/v1/query" in normalized
    assert "do not call admin" in normalized
    assert "do not edit files" in normalized


def test_agents_require_explicit_triggers_and_expert_selection_clarification():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    for trigger in [
        "ask experts panel",
        "experts_panel_researcher",
        "/experts",
        "check through experts panel",
        "панэкс",
        "спроси панэкс",
        "панэнкс",
    ]:
        assert trigger in normalized

    assert "must not query experts panel automatically" in normalized
    assert "generic trends" in normalized
    assert "software" in normalized
    assert "architecture" in normalized
    assert "all" in combined
    assert "group" in combined
    assert "custom" in combined
    assert "ask one clarification" in normalized


def test_agents_normalize_human_expert_names_but_ask_on_ambiguity():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    for alias in [
        "refat",
        "tech_refat",
        "рефат",
        "akimov",
        "biz_akimov",
        "акимов",
        "llm под капотом",
        "ринат",
        "илья измайлов",
        "силикбаг",
        "корнишев",
    ]:
        assert alias in normalized

    assert "ui/display name" in normalized
    assert "preferred user-facing expert names" in normalized
    assert "translate them to expert_id before calling the cli" in normalized
    assert "obvious russian spelling" in normalized
    assert "one-obvious-target typos" in normalized
    assert "could map to more than one expert" in normalized
    assert "ask one clarification before calling the cli" in normalized


def test_agents_pin_production_fly_endpoint_for_real_calls():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "https://experts-panel.fly.dev/api/v1/agent/context" in combined
    assert "--api-url https://experts-panel.fly.dev/api/v1/agent/context" in combined
    assert "fly.io" in normalized
    assert "do not rely on the cli default" in normalized
    assert "use localhost only when" in normalized
    assert "copied into another repository" in normalized


def test_agents_use_source_expand_for_explicit_raw_source_requests():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "src.cli.agent_context_expand" in combined
    assert "https://experts-panel.fly.dev/api/v1/agent/context/expand" in combined
    assert "source_expand" in combined
    assert "source_index" in combined
    assert "source_keys_sent" in combined
    assert "раскрой" in combined
    assert "refat:234" in combined
    assert "not a new expert_digest query" in normalized
    assert "not a new source_bundle query" in normalized


def test_agents_accept_human_russian_triggers_without_requiring_jargon():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "does not need to say" in normalized
    for jargon in [
        "source_key",
        "source_expand",
        "expert_digest",
        "evidence note",
    ]:
        assert jargon in combined.lower()

    for digest_trigger in [
        "панэкс, спроси",
        "что думают эксперты",
        "по мнению экспертов",
        "узнай у <экспертов>",
    ]:
        assert digest_trigger in normalized

    for expansion_trigger in [
        "раскрой подробнее",
        "покажи источники",
        "дай пруфы",
        "на чём основано",
        "почему такой вывод",
        "покажи первоисточник",
        "разверни по <эксперту>",
        "что там в комментариях",
        "проверь источник",
    ]:
        assert expansion_trigger in normalized

    assert "previous digest" in normalized
    assert "latest панэкс expert_digest output available" in normalized
    assert "do not infer handles from memory" in normalized
    assert "source selection priority" in normalized
    assert "concrete source_key" in normalized
    assert "key_signal.supporting_sources" in combined
    assert "digest.source_refs in their existing order" in normalized
    assert "digest.source_index only when" in normalized
    assert "first high / first listed source" in normalized
    assert "supporting_sources" in combined
    assert "top 1 source for each expert" in normalized
    assert "top 1-2 strongest sources" in normalized
    assert "focus the answer on direct comments" in normalized
    assert "supporting practitioner sources" in normalized
    assert "proof of truth" in normalized
    assert "ask one short clarification" in normalized
    assert "a main панэкс question must be asked first" in normalized
    assert "do not run a new expert_digest/source_bundle" in normalized


def test_agents_keep_source_expand_output_as_lean_evidence_note_not_digest():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "lean evidence note" in normalized
    assert "not a new digest/reduce/synthesis" in normalized
    assert "do not rebuild the expert's overall position" in normalized
    assert "what the source itself says" in normalized
    assert "what direct comments add" in normalized
    assert "mostly noise" in normalized
    assert "truncation/limits" in normalized
    assert "3-6 bullets" in normalized
    assert "if the parent asked for raw text" in normalized


def test_agents_surface_evidence_quality_calibration_without_proof_framing():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "evidence_quality" in combined
    assert "evidence quality" in normalized
    assert "strong practical source" in normalized
    assert "announcement/mention" in normalized
    assert "comments mostly noise" in normalized
    assert "calibration, not proof" in normalized
    assert "do not turn labels into proof claims" in normalized


def test_agents_use_signals_frame_instead_of_proof_frame():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    for section in SIGNALS_FRAME_SECTIONS:
        assert section in combined

    assert "must not present practitioner posts as proven facts" in normalized
    assert "practitioner-opinion intelligence" in normalized
    for forbidden_term in FORBIDDEN_PROOF_FRAME_TERMS:
        assert forbidden_term not in combined


def test_agents_include_compact_request_passport_in_query_selection():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "request passport" in normalized
    assert "query and selection" in normalized
    for field in [
        "query_sent",
        "experts_sent",
        "response_mode",
        "target",
        "warnings",
    ]:
        assert field in combined
    assert "do not include the api token" in normalized
    assert "raw json" in normalized
    assert "long pipeline dumps" in normalized


def test_agents_treat_external_links_as_author_references_not_auto_browsing():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "external_links" in combined
    assert "author-supplied references" in normalized
    assert "fetch_status=not_fetched" in normalized
    assert "do not open, fetch, crawl, clone, or summarize external links" in normalized
    assert "explicitly asks for link enrichment or external research" in normalized


def test_agent_files_do_not_store_token_values():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _read(CODEX_AGENT_PATH)])

    assert "AGENT_CONTEXT_API_TOKEN" in combined
    for secret_literal in SECRET_LITERALS:
        assert secret_literal not in combined


def test_spec_records_and9_and_signals_frame_contract():
    spec = _read(SPEC_PATH)
    normalized = _normalize(spec)

    assert "AND-9 `experts_panel_researcher` / `Панэкс` subagent contract" in spec
    assert "Панэкс" in spec
    assert "Панэнкс" in spec
    assert "UI/display labels" in spec
    assert "Russian expert names" in spec
    assert "translate to backend `expert_id`" in spec
    assert "practitioner-opinion intelligence" in normalized
    assert "Request passport" in spec
    for field in [
        "query_sent",
        "experts_sent",
        "response_mode",
        "target",
        "warnings",
    ]:
        assert field in spec
    for section in SIGNALS_FRAME_SECTIONS:
        assert section in spec
    for forbidden_term in FORBIDDEN_PROOF_FRAME_TERMS:
        assert forbidden_term not in spec
