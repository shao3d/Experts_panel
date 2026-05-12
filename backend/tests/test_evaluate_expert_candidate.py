from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "evaluate_expert_candidate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("evaluate_expert_candidate", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_passport(path: Path, expert_id: str, display_name: str, cells: list[dict]):
    payload = {
        "passport_meta": {
            "schema_version": "expert_value_passport.v1.1",
            "expert_id": expert_id,
            "display_name": display_name,
            "channel_username": f"@{expert_id}",
            "generated_at": "2026-05-10T00:00:00+00:00",
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
    intrinsic_distinctiveness: float = 4,
    confidence: float = 4.8,
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
            "intrinsic_distinctiveness": intrinsic_distinctiveness,
            "anti_hype": 4,
            "community_signal": 3,
        },
        "matrix_update_role": "needs_matrix_compare",
        "limitations": [],
        "evidence_refs": ["P0001", "P0002"],
        "confidence": confidence,
    }


def test_candidate_report_detects_gap_and_adjacent_viewpoint(tmp_path):
    module = load_module()
    refat_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    air_path = tmp_path / "air_ai" / "output" / "air_ai_semantic_passport.normalized.json"
    candidate_path = tmp_path / "ai_architect" / "output" / "ai_architect_semantic_passport.normalized.json"
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
        air_path,
        "air_ai",
        "Air",
        [
            make_cell(
                "prompt_engineering/model_specific_formatting/learn_ai_assisted_development",
                "prompt_engineering",
                "model_specific_formatting",
                "learn_ai_assisted_development",
            )
        ],
    )
    write_passport(
        candidate_path,
        "ai_architect",
        "AI Architect",
        [
            make_cell(
                "agent_ops/agentic_dev_process/design_agentic_dev_workflow",
                "agent_ops",
                "agentic_dev_process",
                "design_agentic_dev_workflow",
            ),
            make_cell(
                "coding_agents/codex_workflows/choose_ai_coding_tool",
                "coding_agents",
                "codex_workflows",
                "choose_ai_coding_tool",
            ),
        ],
    )

    report = module.build_candidate_report(candidate_path, [refat_path, air_path])
    impacts = {item["candidate_cell_id"]: item for item in report["cell_impacts"]}

    assert report["summary"]["candidate_cell_count"] == 2
    assert report["summary"]["adds_adjacent_viewpoint_count"] == 1
    assert report["summary"]["fills_gap_count"] == 1
    assert report["summary"]["positive_impact_count"] == 2
    assert report["summary"]["preliminary_recommendation"] == "promising_needs_human_review"
    assert (
        impacts["agent_ops/agentic_dev_process/design_agentic_dev_workflow"]["classification"]
        == "adds_adjacent_viewpoint"
    )
    assert impacts["coding_agents/codex_workflows/choose_ai_coding_tool"]["classification"] == "fills_gap"
    assert report["closest_existing_experts"][0]["expert_id"] == "refat"
    assert report["closest_existing_experts"][0]["related_match_count"] == 1


def test_candidate_report_flags_likely_duplicate_exact_cell(tmp_path):
    module = load_module()
    baseline_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    candidate_path = tmp_path / "candidate" / "output" / "candidate_semantic_passport.normalized.json"
    shared_cell = "agent_ops/claude_code_workflows/design_agentic_dev_workflow"
    write_passport(
        baseline_path,
        "refat",
        "Refat",
        [
            make_cell(
                shared_cell,
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
                source_utility=5,
            )
        ],
    )
    write_passport(
        candidate_path,
        "candidate",
        "Candidate",
        [
            make_cell(
                shared_cell,
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
                source_utility=4.5,
            )
        ],
    )

    report = module.build_candidate_report(candidate_path, [baseline_path])

    assert report["summary"]["likely_duplicate_count"] == 1
    assert report["summary"]["preliminary_recommendation"] == "likely_duplicate_or_low_increment"
    assert report["cell_impacts"][0]["exact_match"]["matrix_cell_id"] == shared_cell


def test_baseline_discovery_uses_accepted_manifest_gate(tmp_path):
    module = load_module()
    accepted_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    rejected_path = tmp_path / "rejected" / "output" / "rejected_semantic_passport.normalized.json"
    candidate_path = tmp_path / "candidate" / "output" / "candidate_semantic_passport.normalized.json"
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
        "rejected",
        "Rejected",
        [
            make_cell(
                "coding_agents/codex_workflows/choose_ai_coding_tool",
                "coding_agents",
                "codex_workflows",
                "choose_ai_coding_tool",
            )
        ],
    )
    write_passport(
        candidate_path,
        "candidate",
        "Candidate",
        [
            make_cell(
                "coding_agents/claude_code_workflows/learn_ai_assisted_development",
                "coding_agents",
                "claude_code_workflows",
                "learn_ai_assisted_development",
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
                "expert_id": "rejected",
                "verdict": "reject",
                "include_in_knowledge_matrix": False,
                "passport_path": str(rejected_path),
            },
            {
                "expert_id": "candidate",
                "verdict": "not_assessed",
                "include_in_knowledge_matrix": False,
                "passport_path": str(candidate_path),
            },
        ],
    )

    baseline_paths = module.discover_baseline_passports(
        tmp_path,
        candidate_path,
        "candidate",
        explicit_baseline_paths=[],
        include_candidate_in_baseline=False,
        admission_manifest_path=manifest_path,
        include_all_baseline_passports=False,
    )
    report = module.build_candidate_report(candidate_path, baseline_paths)

    assert baseline_paths == [accepted_path]
    assert report["baseline"]["summary"]["passport_count"] == 1
    assert report["baseline"]["source_passports"][0]["expert_id"] == "refat"


def test_candidate_report_marks_overlap_heavy_promising_candidate(tmp_path):
    module = load_module()
    baseline_a = tmp_path / "baseline_a" / "output" / "baseline_a_semantic_passport.normalized.json"
    baseline_b = tmp_path / "baseline_b" / "output" / "baseline_b_semantic_passport.normalized.json"
    baseline_c = tmp_path / "baseline_c" / "output" / "baseline_c_semantic_passport.normalized.json"
    candidate_path = tmp_path / "candidate" / "output" / "candidate_semantic_passport.normalized.json"
    write_passport(
        baseline_a,
        "baseline_a",
        "Baseline A",
        [
            make_cell(
                "coding_agents/claude_code_workflows/learn_ai_assisted_development",
                "coding_agents",
                "claude_code_workflows",
                "learn_ai_assisted_development",
            ),
            make_cell(
                "agent_ops/claude_code_workflows/design_agentic_dev_workflow",
                "agent_ops",
                "claude_code_workflows",
                "design_agentic_dev_workflow",
            ),
        ],
    )
    write_passport(
        baseline_b,
        "baseline_b",
        "Baseline B",
        [
            make_cell(
                "coding_agents/codex_workflows/learn_ai_assisted_development",
                "coding_agents",
                "codex_workflows",
                "learn_ai_assisted_development",
            ),
            make_cell(
                "agent_ops/agentic_dev_process/design_agentic_dev_workflow",
                "agent_ops",
                "agentic_dev_process",
                "design_agentic_dev_workflow",
            ),
        ],
    )
    write_passport(
        baseline_c,
        "baseline_c",
        "Baseline C",
        [
            make_cell(
                "ai_product_pm/ai_product_strategy/plan_ai_product_feature",
                "ai_product_pm",
                "ai_product_strategy",
                "plan_ai_product_feature",
            ),
        ],
    )
    write_passport(
        candidate_path,
        "candidate",
        "Candidate",
        [
            make_cell(
                "coding_agents/cursor_windsurf_copilot/learn_ai_assisted_development",
                "coding_agents",
                "cursor_windsurf_copilot",
                "learn_ai_assisted_development",
            ),
            make_cell(
                "agent_ops/multi_agent_orchestration/design_agentic_dev_workflow",
                "agent_ops",
                "multi_agent_orchestration",
                "design_agentic_dev_workflow",
            ),
            make_cell(
                "ai_product_pm/pm_workflow/build_human_ai_workflow",
                "ai_product_pm",
                "pm_workflow",
                "build_human_ai_workflow",
            ),
            make_cell(
                "ai_product_pm/ai_product_strategy/plan_ai_product_feature",
                "ai_product_pm",
                "ai_product_strategy",
                "plan_ai_product_feature",
                source_utility=4.5,
            ),
        ],
    )

    report = module.build_candidate_report(candidate_path, [baseline_a, baseline_b, baseline_c])

    assert report["summary"]["fills_gap_count"] == 1
    assert report["summary"]["adds_adjacent_viewpoint_count"] == 2
    assert report["summary"]["likely_duplicate_count"] == 1
    assert report["summary"]["clean_gap_count"] == 1
    assert report["summary"]["overlap_cell_count"] == 3
    assert report["summary"]["dense_overlap_cell_count"] == 2
    assert report["summary"]["density_caveat"] is True
    assert report["summary"]["preliminary_recommendation"] == "overlap_heavy_needs_stronger_review"


def test_candidate_report_accepts_zero_to_one_confidence_scale(tmp_path):
    module = load_module()
    candidate_path = tmp_path / "candidate" / "output" / "candidate_semantic_passport.normalized.json"
    write_passport(
        candidate_path,
        "candidate",
        "Candidate",
        [
            make_cell(
                "coding_agents/codex_workflows/choose_ai_coding_tool",
                "coding_agents",
                "codex_workflows",
                "choose_ai_coding_tool",
                confidence=0.95,
            )
        ],
    )

    report = module.build_candidate_report(candidate_path, [])

    assert report["cell_impacts"][0]["confidence"] == 0.95
    assert report["cell_impacts"][0]["confidence_normalized_0_5"] == 4.75
    assert report["cell_impacts"][0]["classification"] == "fills_gap"


def test_render_markdown_includes_diagnostic_sections(tmp_path):
    module = load_module()
    candidate_path = tmp_path / "candidate" / "output" / "candidate_semantic_passport.normalized.json"
    write_passport(
        candidate_path,
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

    markdown = module.render_markdown(module.build_candidate_report(candidate_path, []))

    assert "# Candidate Impact Report: Candidate" in markdown
    assert "## Preliminary Recommendation" in markdown
    assert "## Cell Impacts" in markdown
    assert "`fills_gap`" not in markdown
    assert "fills_gap" in markdown
