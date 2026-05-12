from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "build_knowledge_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_knowledge_matrix", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_passport(path: Path, expert_id: str, display_name: str, cells: list[dict]):
    payload = {
        "passport_meta": {
            "expert_id": expert_id,
            "display_name": display_name,
        },
        "matrix_export": {
            "cells": cells,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_manifest(path: Path, entries: list[dict]):
    payload = {
        "schema_version": "expert_admission_manifest.v0.1",
        "experts": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_cell(
    cell_id: str,
    domain_id: str,
    subdomain_id: str,
    query_intent_id: str,
    source_role: str = "primary",
    source_utility: float = 5,
) -> dict:
    return {
        "cell_id": cell_id,
        "domain_id": domain_id,
        "subdomain_id": subdomain_id,
        "subdomain_name": subdomain_id.replace("_", " ").title(),
        "query_intent_ids": [query_intent_id],
        "source_role": source_role,
        "coverage_level": "strong",
        "depth_level": "deep_practitioner",
        "scores": {
            "depth": 5,
            "practicality": 5,
            "evidence_quality": 5,
            "source_utility": source_utility,
            "intrinsic_distinctiveness": 4,
            "anti_hype": 4,
            "community_signal": 3,
        },
        "matrix_update_role": "needs_matrix_compare",
        "limitations": [],
        "evidence_refs": ["P0001"],
        "confidence": 0.9,
    }


def test_build_matrix_groups_cells_and_flags_taxonomy_extensions(tmp_path):
    module = load_module()
    refat_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    air_path = tmp_path / "air_ai" / "output" / "air_ai_semantic_passport.normalized.json"
    shared_cell_id = "agent_ops/claude_code_workflows/design_agentic_dev_workflow"
    write_passport(
        refat_path,
        "refat",
        "Refat",
        [
            make_cell(
                shared_cell_id,
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
                source_utility=5,
            )
        ],
    )
    write_passport(
        air_path,
        "air_ai",
        "Air",
        [
            make_cell(
                shared_cell_id,
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
                source_role="supporting",
                source_utility=4,
            ),
            make_cell(
                "prompt_engineering/model_specific_formatting/learn_ai_assisted_development",
                "prompt_engineering",
                "model_specific_formatting",
                "learn_ai_assisted_development",
            ),
            make_cell(
                "ai_business_adoption/financial_modeling/assess_ai_tool_business_adoption",
                "ai_business_adoption",
                "financial_modeling",
                "assess_ai_tool_business_adoption",
            ),
            make_cell(
                "ai_engineering_infra/local_hardware/optimize_inference_cost_latency",
                "ai_engineering_infra",
                "local_hardware",
                "optimize_inference_cost_latency",
            ),
        ],
    )

    matrix = module.build_matrix([refat_path, air_path])
    cells = {cell["matrix_cell_id"]: cell for cell in matrix["cells"]}
    applied_aliases = {
        (item["kind"], item["from"], item["to"])
        for item in matrix["taxonomy_review"]["applied_aliases"]
    }

    assert matrix["summary"]["passport_count"] == 2
    assert matrix["summary"]["matrix_cell_count"] == 4
    assert matrix["summary"]["taxonomy_extension_count"] == 0
    assert matrix["summary"]["applied_alias_count"] == 2
    assert matrix["summary"]["related_cell_overlap_count"] == 0
    assert cells[shared_cell_id]["expert_count"] == 2
    assert cells[shared_cell_id]["redundancy_level"] == "low"
    assert cells[shared_cell_id]["coverage_status"] == "strong_single_source"
    assert cells[shared_cell_id]["best_experts"][0]["expert_id"] == "refat"
    assert (
        "business_adoption/financial_modeling/assess_ai_tool_business_adoption"
        in cells
    )
    assert "ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency" in cells
    assert ("domain", "ai_business_adoption", "business_adoption") in applied_aliases
    assert ("subdomain", "local_hardware", "inference_cost_latency") in applied_aliases
    assert matrix["taxonomy_review"]["proposed_extensions"] == []
    rollups = {item["rollup_id"]: item for item in matrix["rollups"]["domain_query_intent"]}
    assert rollups["agent_ops/design_agentic_dev_workflow"]["overlap_status"] == "exact_multi_source"
    assert rollups["agent_ops/design_agentic_dev_workflow"]["exact_cell_count"] == 1


def test_build_matrix_adds_related_cell_overlap_rollup(tmp_path):
    module = load_module()
    refat_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    ai_arch_path = tmp_path / "ai_architect" / "output" / "ai_architect_semantic_passport.normalized.json"
    write_passport(
        refat_path,
        "refat",
        "Refat",
        [
            make_cell(
                "agent_ops/claude_code_workflows/design_agentic_dev_workflow",
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
            )
        ],
    )
    write_passport(
        ai_arch_path,
        "ai_architect",
        "AI Architect",
        [
            make_cell(
                "agent_ops/agentic_dev_process/design_agentic_dev_workflow",
                "agent_ops",
                "agentic_dev_process",
                "design_agentic_dev_workflow",
            )
        ],
    )

    matrix = module.build_matrix([refat_path, ai_arch_path])
    rollups = {item["rollup_id"]: item for item in matrix["rollups"]["domain_query_intent"]}
    overlap = matrix["related_cell_overlaps"][0]

    assert matrix["summary"]["matrix_cell_count"] == 2
    assert matrix["summary"]["strong_multi_source_count"] == 0
    assert matrix["summary"]["related_cell_overlap_count"] == 1
    assert matrix["summary"]["strong_domain_intent_multi_source_count"] == 1
    assert rollups["agent_ops/design_agentic_dev_workflow"]["overlap_status"] == "related_multi_source"
    assert rollups["agent_ops/design_agentic_dev_workflow"]["coverage_status"] == "strong_multi_source"
    assert rollups["agent_ops/design_agentic_dev_workflow"]["exact_cell_count"] == 2
    assert overlap["rollup_id"] == "agent_ops/design_agentic_dev_workflow"
    assert overlap["decision_hint"] == "review_overlap_or_complement_before_counting_as_new_gap"


def test_discover_accepted_passports_uses_admission_manifest_gate(tmp_path):
    module = load_module()
    accepted_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    rejected_path = tmp_path / "candidate" / "output" / "candidate_semantic_passport.normalized.json"
    write_passport(
        accepted_path,
        "refat",
        "Refat",
        [
            make_cell(
                "agent_ops/claude_code_workflows/design_agentic_dev_workflow",
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
            )
        ],
    )
    write_passport(
        rejected_path,
        "candidate",
        "Candidate",
        [
            make_cell(
                "coding_agents/codex_workflows/choose_ai_coding_tool",
                "coding_agents",
                "codex_workflows",
                "choose_ai_coding_tool",
            )
        ],
    )
    manifest_path = tmp_path / "admission_manifest.json"
    write_manifest(
        manifest_path,
        [
            {
                "expert_id": "refat",
                "verdict": "accept",
                "include_in_knowledge_matrix": True,
                "passport_path": str(accepted_path),
            },
            {
                "expert_id": "candidate",
                "verdict": "reject",
                "include_in_knowledge_matrix": False,
                "passport_path": str(rejected_path),
            },
        ],
    )

    selected = module.discover_accepted_passports(tmp_path, manifest_path)
    matrix = module.build_matrix(selected)

    assert selected == [accepted_path]
    assert matrix["summary"]["passport_count"] == 1
    assert matrix["summary"]["matrix_cell_count"] == 1
    assert matrix["source_passports"][0]["expert_id"] == "refat"


def test_render_markdown_includes_summary_and_taxonomy_review(tmp_path):
    module = load_module()
    passport_path = tmp_path / "air_ai" / "output" / "air_ai_semantic_passport.normalized.json"
    write_passport(
        passport_path,
        "air_ai",
        "Air",
        [
            make_cell(
                "ai_business_adoption/financial_modeling/assess_ai_tool_business_adoption",
                "ai_business_adoption",
                "financial_modeling",
                "assess_ai_tool_business_adoption",
            )
        ],
    )

    markdown = module.render_markdown(module.build_matrix([passport_path]))

    assert "# Knowledge Matrix v0.3" in markdown
    assert "## Domain + Intent Rollups" in markdown
    assert "`ai_business_adoption/financial_modeling/assess_ai_tool_business_adoption`" in markdown
    assert "`business_adoption/financial_modeling/assess_ai_tool_business_adoption`" in markdown
    assert "`ai_business_adoption`" in markdown
    assert "alias_to_business_adoption" in markdown
