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

DELIVERY_FRAME_SECTIONS = [
    "Request passport",
    "Expert digest delivery",
    "Scope and warnings",
    "Expansion candidates",
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
    assert "panex ask" in content
    assert "panex expand" in content
    assert "--response-mode source_bundle" in content
    assert "expert_digest" in content
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
    assert "panex ask" in instructions
    assert "panex expand" in instructions
    assert "--response-mode source_bundle" in instructions
    assert "expert_digest" in instructions
    assert "source_bundle" in instructions
    assert "explicit" in normalized
    assert "do not call /api/v1/query" in normalized
    assert "do not call admin" in normalized
    assert "do not edit files" in normalized


def test_agent_metadata_routes_panex_to_subagent_before_direct_cli():
    claude_content = _read(CLAUDE_AGENT_PATH)
    config = _codex_agent_config()
    combined = "\n".join([claude_content, config["developer_instructions"]])
    normalized = _normalize(combined)

    assert "панэкс" in config["description"].lower()
    assert "panex" in [candidate.lower() for candidate in config["nickname_candidates"]]
    assert "panenx" in [candidate.lower() for candidate in config["nickname_candidates"]]
    assert all(
        re.fullmatch(r"[A-Za-z0-9 _-]+", candidate)
        for candidate in config["nickname_candidates"]
    )
    assert "панэкс" in claude_content.split("---", 2)[1].lower()
    assert "parent routing contract" in normalized
    assert "prefer experts_panel_researcher" in normalized
    assert "over direct panex cli" in normalized
    assert "direct cli is a fallback" in normalized
    assert "--save --receipt-json" in combined
    assert "panex read" in combined
    assert "panex export" in combined
    assert "do not dump raw stdout" in normalized
    assert "do not call panex automatically" in normalized


def test_agent_keeps_project_applicability_in_parent_chat():
    claude_content = _read(CLAUDE_AGENT_PATH)
    config = _codex_agent_config()
    combined = "\n".join([claude_content, config["developer_instructions"]])
    normalized = _normalize(combined)

    assert "research/retrieval agent only" in normalized
    assert "parent project's context only as a retrieval lens" in normalized
    assert "do not make project-specific pm" in normalized
    assert "go/no-go" in normalized
    assert "implementation recommendations for the parent project" in normalized
    assert "final applicability analysis belongs in the parent chat" in normalized
    assert "the parent chat applies them to the current project" in normalized
    assert "teya" not in normalized


def test_agents_use_artifact_transport_for_real_panex_calls():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "--save --receipt-json" in combined
    assert "panex read" in combined
    assert "never use cat" in normalized
    assert "saved panex artifacts" in normalized
    assert "before final synthesis" in normalized
    assert "read the saved artifact" in normalized
    assert "artifact_path" in combined
    assert "response_bytes" in combined
    assert "write only panex artifacts" in normalized
    assert "must not edit repo files" in normalized


def test_agents_wait_patiently_after_submitting_long_running_panex_request():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "long-running request discipline" in normalized
    assert "single in-flight request" in normalized
    assert "do not start a duplicate" in normalized
    assert "reset state" in normalized
    assert "restart fly machines" in normalized
    assert "rerun update scripts" in normalized
    assert "read-only monitoring" in normalized
    assert "fly status --app experts-panel" in combined
    assert "timeout 10 fly logs --app experts-panel" in combined
    assert "https://experts-panel.fly.dev/api/info" in combined
    assert "https://experts-panel.fly.dev/api/v1/experts" in combined
    assert "no more than once every 30-60 seconds" in normalized
    assert "still processing" in normalized
    assert "do not retry without explicit parent approval" in normalized


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


def test_agents_answer_help_requests_without_api_calls():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    for phrase in [
        "панэкс, помощь",
        "панэкс, что ты умеешь",
        "как пользоваться панэксом",
        "покажи примеры панэкса",
        "как искать через панэкс",
    ]:
        assert phrase in normalized

    assert "do not call panex ask" in normalized
    assert "panex expand" in normalized
    assert "or any api" in normalized
    assert "panex guide" in normalized
    assert "explicit-only boundary" in normalized
    assert "source_bundle as explicit raw/audit" in normalized
    assert "external links as references-only" in normalized
    assert "drift comment groups not selected by default" in normalized


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
    assert "panex ask" in combined
    assert "panex" in normalized
    assert "defaults to the fly.io urls" in normalized
    assert "ignores ambient local" in normalized
    assert "fly.io" in normalized
    assert "lower-level" in normalized
    assert "src.cli.agent_context" in combined
    assert "defaults for real user calls" in normalized
    assert "use localhost only when" in normalized
    assert "copied into another repository" in normalized
    assert "panex doctor" in normalized


def test_agents_use_source_expand_for_explicit_raw_source_requests():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "panex expand" in combined
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
        "самый сильный источник",
        "самый слабый источник",
        "самый спорный источник",
        "слабые места",
        "проверь источник",
    ]:
        assert expansion_trigger in normalized

    assert "previous digest" in normalized
    assert "latest панэкс expert_digest output available" in normalized
    assert "do not infer handles from memory" in normalized
    assert "source selection priority" in normalized
    assert "explicit source_key" in normalized
    assert "key_signal.supporting_sources" in combined
    assert "referenced claim" in normalized
    assert "digest.source_refs in their existing order" in normalized
    assert "selector words such as strongest/weakest/controversial/comments" in normalized
    assert "then clarification" in normalized
    assert "can point to several key_signals" in normalized
    assert "one specific claim or source handle" in normalized
    assert "first high / first listed source" in normalized
    assert "weakest" in normalized
    assert "слабые места" in normalized
    assert "самый спорный" in normalized
    assert "evidence_quality" in normalized
    assert "caveats" in normalized
    assert "comments signals" in normalized
    assert "do not invent a fresh ranking" in normalized
    assert "supporting_sources" in combined
    assert "top 1 source for each expert" in normalized
    assert "names one expert" in normalized
    assert "top 1 source unless" in normalized
    assert "top 1-2 strongest sources" in normalized
    assert "never expand all sources by default" in normalized
    assert "все источники" in normalized
    assert "raw по всем" in normalized
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
    assert "intentionally different from the digest request passport" in normalized
    assert "does not need query_sent" in normalized
    assert "does not need experts_sent" in normalized
    assert "limits_used" in normalized
    assert "what the source itself says" in normalized
    assert "what direct comments add" in normalized
    assert "mostly noise" in normalized
    assert "truncation flags" in normalized
    assert "3-6 bullets" in normalized
    assert "if the parent asked for raw text" in normalized


def test_agents_default_to_relay_only_digest_delivery():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "relay-only" in normalized
    assert "do not summarize the digest again" in normalized
    assert "do not create a new meta-synthesis" in normalized
    assert "deliver backend digest fields" in normalized
    assert "digest.position" in combined
    assert "digest.key_signals" in combined
    assert "digest.source_refs" in combined
    assert "digest.omitted_counts" in combined
    assert "digest.limits_used" in combined
    assert "artifact/export files" in normalized
    assert "must not replace the saved digest" in normalized
    assert "expansion candidates" in normalized
    assert "signals frame" not in normalized
    assert "convert it into a compact signals frame" not in normalized
    assert "practical decision bullets" not in normalized
    assert "practical application" not in combined
    assert "weak, indirect, or comment-heavy" in normalized
    assert "proof-style headings" in normalized


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


def test_agents_use_delivery_frame_instead_of_proof_frame():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    for section in DELIVERY_FRAME_SECTIONS:
        assert section in combined

    assert "must not present practitioner posts as proven facts" in normalized
    assert "practitioner-opinion intelligence" in normalized
    for forbidden_term in FORBIDDEN_PROOF_FRAME_TERMS:
        assert forbidden_term not in combined


def test_agents_include_compact_request_passport_in_digest_delivery():
    combined = "\n".join([_read(CLAUDE_AGENT_PATH), _codex_agent_config()["developer_instructions"]])
    normalized = _normalize(combined)

    assert "request passport" in normalized
    assert "must begin the answer" in normalized
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


def test_spec_records_and9_and_delivery_frame_contract():
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
    for section in DELIVERY_FRAME_SECTIONS:
        assert section in spec
    for forbidden_term in FORBIDDEN_PROOF_FRAME_TERMS:
        assert forbidden_term not in spec
