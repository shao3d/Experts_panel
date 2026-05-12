from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "calibrate_candidate_evaluator.py"


def load_module():
    spec = importlib.util.spec_from_file_location("calibrate_candidate_evaluator", SCRIPT_PATH)
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


def make_cell(cell_id: str, domain_id: str, subdomain_id: str, query_intent_id: str) -> dict:
    return {
        "cell_id": cell_id,
        "domain_id": domain_id,
        "subdomain_id": subdomain_id,
        "subdomain_name": subdomain_id.replace("_", " ").title(),
        "query_intent_ids": [query_intent_id],
        "source_role": "primary",
        "coverage_level": "strong",
        "depth_level": "deep_practitioner",
        "scores": {
            "depth": 5,
            "practicality": 5,
            "evidence_quality": 5,
            "source_utility": 5,
            "intrinsic_distinctiveness": 4,
            "anti_hype": 4,
            "community_signal": 3,
        },
        "matrix_update_role": "needs_matrix_compare",
        "limitations": [],
        "evidence_refs": ["P0001", "P0002"],
        "confidence": 4.8,
    }


def fixture_passports(tmp_path: Path) -> list[Path]:
    refat_path = tmp_path / "refat" / "output" / "refat_semantic_passport.normalized.json"
    ai_arch_path = tmp_path / "ai_architect" / "output" / "ai_architect_semantic_passport.normalized.json"
    air_path = tmp_path / "air_ai" / "output" / "air_ai_semantic_passport.normalized.json"
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
            ),
            make_cell(
                "rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base",
                "rag_retrieval_knowledge",
                "knowledge_base_design",
                "design_rag_knowledge_base",
            ),
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
            ),
            make_cell(
                "coding_agents/codex_workflows/choose_ai_coding_tool",
                "coding_agents",
                "codex_workflows",
                "choose_ai_coding_tool",
            ),
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
            ),
            make_cell(
                "business_adoption/financial_modeling/assess_ai_tool_business_adoption",
                "business_adoption",
                "financial_modeling",
                "assess_ai_tool_business_adoption",
            ),
        ],
    )
    return [refat_path, ai_arch_path, air_path]


def test_build_calibration_runs_leave_one_out_cases(tmp_path):
    module = load_module()
    calibration = module.build_calibration(fixture_passports(tmp_path))
    cases = {case["candidate_expert_id"]: case for case in calibration["cases"]}

    assert calibration["schema_version"] == "candidate_evaluator_calibration.v0.1"
    assert calibration["aggregate"]["case_count"] == 3
    assert calibration["aggregate"]["total_candidate_cells"] == 6
    assert calibration["aggregate"]["total_related_overlaps"] == 2
    assert calibration["aggregate"]["classification_totals"]["adds_adjacent_viewpoint"] == 2
    assert calibration["aggregate"]["classification_totals"]["fills_gap"] == 4
    assert calibration["aggregate"]["cases_with_no_positive_impact"] == []
    assert cases["ai_architect"]["baseline_passport_count"] == 2
    assert cases["ai_architect"]["classification_counts"]["adds_adjacent_viewpoint"] == 1
    assert cases["air_ai"]["classification_counts"]["fills_gap"] == 2
    assert cases["refat"]["classification_counts"]["adds_adjacent_viewpoint"] == 1


def test_write_calibration_artifacts_writes_summary_and_per_candidate_reports(tmp_path):
    module = load_module()
    calibration = module.build_calibration(fixture_passports(tmp_path / "input"))
    paths = module.write_calibration_artifacts(calibration, tmp_path / "out")

    assert paths["json"].exists()
    assert paths["markdown"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert payload["aggregate"]["case_count"] == 3
    assert "# Candidate Evaluator Leave-One-Out Calibration" in markdown
    assert "`ai_architect`" in markdown
    assert (tmp_path / "out" / "per_candidate" / "ai_architect" / "candidate_impact_report.md").exists()
