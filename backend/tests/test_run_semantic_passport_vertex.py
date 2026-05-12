from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_semantic_passport_vertex.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_semantic_passport_vertex", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_passport_hydrates_missing_source_refs_and_generated_at():
    module = load_module()
    source_ref_index = [
        {
            "source_ref": "P0001",
            "source_kind": "expert_post",
            "post_id": 1,
            "telegram_message_id": 101,
            "comment_id": None,
            "telegram_comment_id": None,
            "created_at": "2026-05-01 10:00:00",
            "char_count": 100,
        },
        {
            "source_ref": "P0001.C0001",
            "source_kind": "community_comment",
            "post_id": 1,
            "telegram_message_id": 101,
            "comment_id": 10,
            "telegram_comment_id": 1001,
            "created_at": "2026-05-01 11:00:00",
            "char_count": 20,
        },
    ]
    passport = {
        "passport_meta": {"generated_at": "2023-01-01T00:00:00Z"},
        "corpus_audit": {},
        "source_ref_index_used": [
            {
                "source_ref": "P0001",
                "source_kind": "expert_post",
                "post_id": 1,
                "telegram_message_id": 101,
                "comment_id": None,
                "telegram_comment_id": None,
                "created_at": "2026-05-01 10:00:00",
                "why_used": "Primary post.",
            }
        ],
        "executive_summary": {},
        "expert_positioning": {},
        "knowledge_domains": [{"evidence_refs": ["P0001"]}],
        "value_dimensions": [],
        "matrix_cells": [],
        "query_intent_fit": [],
        "content_quality_distribution": [],
        "matrix_export": {
            "cells": [{"evidence_refs": ["P0001.C0001"]}],
        },
        "signature_insights": [],
        "practical_patterns": [],
        "claims_and_positions": [],
        "source_utility": {},
        "community_signal": {},
        "admission_implications": {},
        "audit": {},
    }

    expected_generated_at = "2026-05-09T16:24:53+00:00"
    validation_before = module.validate_passport(
        passport,
        source_ref_index,
        expected_generated_at=expected_generated_at,
    )
    normalized = module.normalize_passport(
        passport,
        source_ref_index,
        expected_generated_at=expected_generated_at,
    )
    validation_after = module.validate_passport(
        normalized,
        source_ref_index,
        expected_generated_at=expected_generated_at,
    )

    assert validation_before["valid_basic_contract"] is False
    assert validation_before["refs_missing_from_source_ref_index_used"] == ["P0001.C0001"]
    assert validation_after["valid_basic_contract"] is True
    assert normalized["passport_meta"]["generated_at"] == expected_generated_at
    assert {entry["source_ref"] for entry in normalized["source_ref_index_used"]} == {
        "P0001",
        "P0001.C0001",
    }


def test_normalize_passport_repairs_strong_matrix_cells_missing_from_export():
    module = load_module()
    source_ref_index = [
        {
            "source_ref": "P0002",
            "source_kind": "expert_post",
            "post_id": 2,
            "telegram_message_id": 102,
            "comment_id": None,
            "telegram_comment_id": None,
            "created_at": "2026-05-02 10:00:00",
            "char_count": 100,
        }
    ]
    passport = {
        "passport_meta": {"generated_at": "2023-01-01T00:00:00Z"},
        "corpus_audit": {},
        "source_ref_index_used": [],
        "executive_summary": {},
        "expert_positioning": {},
        "knowledge_domains": [],
        "value_dimensions": [],
        "matrix_cells": [
            {
                "domain_id": "prompt_engineering",
                "subdomain_id": "context_compression",
                "subdomain_name": "Context Compression",
                "query_intent_ids": ["optimize_inference_cost_latency"],
                "depth_score_0_5": 5,
                "practicality_score_0_5": 5,
                "intrinsic_distinctiveness_score_0_5": 5,
                "matrix_relative_novelty": "not_scored_without_matrix",
                "evidence_quality_score_0_5": 5,
                "source_utility_score_0_5": 5,
                "comment_signal_score_0_5": 4,
                "recommended_matrix_weight": "signature",
                "evidence_refs": ["P0002"],
            }
        ],
        "query_intent_fit": [],
        "content_quality_distribution": [],
        "matrix_export": {
            "schema_version": "knowledge_matrix_export.v1",
            "expert_id": "candidate",
            "cells": [],
            "compare_hints": {},
        },
        "signature_insights": [],
        "practical_patterns": [],
        "claims_and_positions": [],
        "source_utility": {},
        "community_signal": {},
        "admission_implications": {},
        "audit": {},
    }

    expected_generated_at = "2026-05-09T16:24:53+00:00"
    validation_before = module.validate_passport(
        passport,
        source_ref_index,
        expected_generated_at=expected_generated_at,
    )
    normalized = module.normalize_passport(
        passport,
        source_ref_index,
        expected_generated_at=expected_generated_at,
    )
    validation_after = module.validate_passport(
        normalized,
        source_ref_index,
        expected_generated_at=expected_generated_at,
    )

    assert validation_before["matrix_export_incomplete"] is True
    assert validation_before["missing_matrix_export_cell_count"] == 1
    assert validation_before["valid_basic_contract"] is False
    assert validation_after["matrix_export_incomplete"] is False
    assert validation_after["valid_basic_contract"] is True
    assert normalized["matrix_export"]["cells"][0]["cell_id"] == (
        "prompt_engineering/context_compression/optimize_inference_cost_latency"
    )
    assert normalized["matrix_export"]["cells"][0]["derived_from"] == "matrix_cells"
