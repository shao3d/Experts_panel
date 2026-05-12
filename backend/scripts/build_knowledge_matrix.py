#!/usr/bin/env python3
"""Build the knowledge matrix from normalized semantic passports.

The matrix is a deterministic aggregation layer over LLM-generated passports.
It does not call Vertex AI. It groups `matrix_export.cells`, flags taxonomy
extensions, computes exact-cell coverage, and adds rollups that expose related
coverage across nearby cells.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_INPUT_ROOT = REPO_ROOT / "output" / "expert_admission" / "semantic_passports"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "expert_admission" / "knowledge_matrix"
DEFAULT_ADMISSION_MANIFEST = REPO_ROOT / "output" / "expert_admission" / "admission_manifest.json"
ACCEPTED_VERDICTS = {"accept", "limited_scope"}


CORE_DOMAIN_IDS = {
    "coding_agents",
    "agent_ops",
    "evals_quality",
    "rag_retrieval_knowledge",
    "prompt_engineering",
    "ai_product_pm",
    "business_adoption",
    "ai_ux_workflow",
    "security_privacy_governance",
    "ai_engineering_infra",
    "model_landscape",
    "creative_multimodal",
    "general_ai_news",
    "other_distinctive_domain",
}

CORE_SUBDOMAIN_IDS = {
    "ai_coding_ides",
    "claude_code_workflows",
    "codex_workflows",
    "cursor_windsurf_copilot",
    "agentic_dev_process",
    "code_review_testing",
    "mcp_tooling",
    "local_agent_setup",
    "multi_agent_orchestration",
    "tool_calling_hooks_skills",
    "llm_evals",
    "regression_harness",
    "benchmark_interpretation",
    "quality_gates",
    "rag_architecture",
    "hybrid_retrieval",
    "embeddings_vector_search",
    "knowledge_base_design",
    "model_specific_formatting",
    "context_compression",
    "reasoning_control",
    "ai_product_strategy",
    "pm_workflow",
    "adoption_roadmaps",
    "roi_business_cases",
    "financial_modeling",
    "human_ai_workflow",
    "ai_ux_patterns",
    "security_privacy_controls",
    "governance_risk",
    "inference_cost_latency",
    "deployment_observability",
    "model_comparison",
    "model_release_analysis",
    "multimodal_generation",
    "broad_ai_news",
}

CORE_QUERY_INTENT_IDS = {
    "choose_ai_coding_tool",
    "design_agentic_dev_workflow",
    "debug_agent_failure",
    "build_ai_dev_eval",
    "design_rag_knowledge_base",
    "improve_retrieval_quality",
    "plan_ai_product_feature",
    "assess_ai_tool_business_adoption",
    "manage_security_privacy_governance",
    "compare_models_for_task",
    "optimize_inference_cost_latency",
    "build_human_ai_workflow",
    "learn_ai_assisted_development",
}

DOMAIN_ALIASES = {
    "ai_business_adoption": "business_adoption",
}

SUBDOMAIN_ALIASES: dict[str, str] = {
    "architecture": "tool_calling_hooks_skills",
    "graph_rag_legal": "rag_architecture",
    "local_hardware": "inference_cost_latency",
}

TAXONOMY_DECISIONS = [
    {
        "value": "prompt_engineering",
        "kind": "domain",
        "decision": "promote_to_core",
        "rationale": "Air shows model-specific prompt formatting as a primary source role, distinct from generic UX/workflow.",
    },
    {
        "value": "model_specific_formatting",
        "kind": "subdomain",
        "decision": "promote_to_core",
        "rationale": "This is a reusable Panex query surface: how prompt structure changes across Claude/Gemini/GPT.",
    },
    {
        "value": "context_compression",
        "kind": "subdomain",
        "decision": "promote_to_core",
        "rationale": "Glebkudr shows context compression as a recurring AI-assisted development problem: packaging large repos, pruning attention, and controlling token cost without losing task-relevant codebase semantics.",
    },
    {
        "value": "reasoning_control",
        "kind": "subdomain",
        "decision": "promote_to_core",
        "rationale": "Air shows reasoning-control prompting as a reusable query surface: premortems, role/process separation, and techniques for steering reasoning depth rather than only formatting prompts.",
    },
    {
        "value": "financial_modeling",
        "kind": "subdomain",
        "decision": "promote_to_core",
        "rationale": "Financial modeling is a concrete high-value business workflow, not just generic ROI discussion.",
    },
    {
        "value": "ai_business_adoption",
        "kind": "domain",
        "decision": "alias_to_business_adoption",
        "rationale": "The existing business_adoption domain already covers business workflows and adoption economics.",
    },
    {
        "value": "architecture",
        "kind": "subdomain",
        "decision": "alias_to_tool_calling_hooks_skills",
        "rationale": "Kovalskii uses the generic label for SGR vs Function Calling architecture; the existing tool_calling_hooks_skills subdomain preserves the concrete mechanism.",
    },
    {
        "value": "local_hardware",
        "kind": "subdomain",
        "decision": "alias_to_inference_cost_latency",
        "rationale": "Kovalskii's local hardware posts are mainly about vLLM/LiteLLM, GPU sizing, throughput, and cost/latency trade-offs.",
    },
    {
        "value": "graph_rag_legal",
        "kind": "subdomain",
        "decision": "alias_to_rag_architecture",
        "rationale": "Air's legal GraphRAG cell is a domain-specific GraphRAG/RAG architecture pattern, not a reusable top-level Experts Panel subdomain.",
    },
]

SCORE_KEYS = (
    "depth",
    "practicality",
    "evidence_quality",
    "source_utility",
    "intrinsic_distinctiveness",
    "anti_hype",
    "community_signal",
)

ROLLUP_KINDS = ("domain", "domain_query_intent", "query_intent")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def discover_passports(input_root: Path) -> list[Path]:
    return sorted(input_root.glob("*/output/*_semantic_passport.normalized.json"))


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def normalize_manifest_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries = manifest.get("experts") or []
    if isinstance(entries, dict):
        return [
            {
                "expert_id": expert_id,
                **entry,
            }
            for expert_id, entry in entries.items()
        ]
    return list(entries)


def admission_manifest_entries(manifest_path: Path) -> list[dict[str, Any]]:
    return normalize_manifest_entries(read_json(manifest_path))


def manifest_entry_included(entry: dict[str, Any], accepted_verdicts: set[str]) -> bool:
    explicit_include = entry.get("include_in_knowledge_matrix")
    if explicit_include is not None:
        return bool(explicit_include)
    return entry.get("verdict") in accepted_verdicts


def manifest_passport_path(entry: dict[str, Any], input_root: Path) -> Path:
    if entry.get("passport_path"):
        return resolve_repo_path(entry["passport_path"])

    expert_id = entry.get("expert_id")
    if not expert_id:
        raise ValueError("Admission manifest entry is missing expert_id.")
    return input_root / expert_id / "output" / f"{expert_id}_semantic_passport.normalized.json"


def discover_accepted_passports(input_root: Path, manifest_path: Path) -> list[Path]:
    manifest = read_json(manifest_path)
    accepted_verdicts = set(manifest.get("accepted_verdicts") or ACCEPTED_VERDICTS)
    missing: list[Path] = []
    selected: list[Path] = []

    for entry in normalize_manifest_entries(manifest):
        if not manifest_entry_included(entry, accepted_verdicts):
            continue
        path = manifest_passport_path(entry, input_root)
        if not path.exists():
            missing.append(path)
            continue
        selected.append(path)

    if missing:
        missing_lines = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(
            f"Admission manifest references missing accepted passport(s):\n{missing_lines}"
        )
    return sorted(selected)


def select_passports(
    input_root: Path,
    explicit_passports: list[Path] | None = None,
    admission_manifest_path: Path | None = DEFAULT_ADMISSION_MANIFEST,
    include_all_passports: bool = False,
) -> list[Path]:
    if explicit_passports:
        return explicit_passports
    if (
        not include_all_passports
        and admission_manifest_path is not None
        and admission_manifest_path.exists()
    ):
        return discover_accepted_passports(input_root, admission_manifest_path)
    return discover_passports(input_root)


def score_contributor(contributor: dict[str, Any]) -> float:
    scores = contributor["scores"]
    return round(
        (
            scores.get("source_utility", 0) * 1.3
            + scores.get("evidence_quality", 0) * 1.2
            + scores.get("depth", 0)
            + scores.get("practicality", 0)
            + scores.get("intrinsic_distinctiveness", 0) * 0.8
        )
        / 5.3,
        3,
    )


def best_contributors_by_expert(contributors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_expert: dict[str, dict[str, Any]] = {}
    for item in contributors:
        existing = best_by_expert.get(item["expert_id"])
        if existing is None:
            best_by_expert[item["expert_id"]] = item
            continue
        item_rank = (
            item["aggregate_score"],
            item["source_role"] == "primary",
            item.get("confidence") or 0,
        )
        existing_rank = (
            existing["aggregate_score"],
            existing["source_role"] == "primary",
            existing.get("confidence") or 0,
        )
        if item_rank > existing_rank:
            best_by_expert[item["expert_id"]] = item
    return list(best_by_expert.values())


def best_experts_payload(contributors: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    best_experts = sorted(
        contributors,
        key=lambda item: (item["aggregate_score"], item.get("confidence") or 0),
        reverse=True,
    )
    return [
        {
            "expert_id": item["expert_id"],
            "display_name": item["display_name"],
            "source_role": item["source_role"],
            "aggregate_score": item["aggregate_score"],
            "evidence_ref_count": len(item["evidence_refs"]),
        }
        for item in best_experts[:limit]
    ]


def score_summary_payload(contributors: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        score_key: {
            "avg": round(mean(item["scores"].get(score_key, 0) for item in contributors), 3),
            "max": max(item["scores"].get(score_key, 0) for item in contributors),
        }
        for score_key in SCORE_KEYS
    }


def cell_key(cell: dict[str, Any]) -> str:
    query_intent_ids = cell.get("query_intent_ids") or ["unknown_query_intent"]
    return f"{cell.get('domain_id', 'unknown_domain')}/{cell.get('subdomain_id', 'unknown_subdomain')}/{query_intent_ids[0]}"


def normalize_cell(cell: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = json.loads(json.dumps(cell, ensure_ascii=False))
    aliases: list[dict[str, Any]] = []

    original_domain_id = normalized.get("domain_id")
    canonical_domain_id = DOMAIN_ALIASES.get(original_domain_id, original_domain_id)
    if canonical_domain_id != original_domain_id:
        aliases.append(
            {
                "kind": "domain",
                "from": original_domain_id,
                "to": canonical_domain_id,
                "cell_id": normalized.get("cell_id"),
            }
        )
        normalized["domain_id"] = canonical_domain_id

    original_subdomain_id = normalized.get("subdomain_id")
    canonical_subdomain_id = SUBDOMAIN_ALIASES.get(original_subdomain_id, original_subdomain_id)
    if canonical_subdomain_id != original_subdomain_id:
        aliases.append(
            {
                "kind": "subdomain",
                "from": original_subdomain_id,
                "to": canonical_subdomain_id,
                "cell_id": normalized.get("cell_id"),
            }
        )
        normalized["subdomain_id"] = canonical_subdomain_id

    if aliases:
        normalized["original_cell_id"] = normalized.get("cell_id")
        normalized["cell_id"] = cell_key(normalized)

    return normalized, aliases


def classify_coverage(contributors: list[dict[str, Any]]) -> str:
    if not contributors:
        return "none"
    primary_count = sum(1 for item in contributors if item["source_role"] == "primary")
    best = max(score_contributor(item) for item in contributors)
    if primary_count >= 2 and best >= 4.3:
        return "strong_multi_source"
    if primary_count >= 1 and best >= 4.3:
        return "strong_single_source"
    if best >= 3.5:
        return "moderate"
    return "thin"


def classify_redundancy(contributors: list[dict[str, Any]]) -> str:
    strong_count = sum(1 for item in contributors if score_contributor(item) >= 4.0)
    if strong_count >= 4:
        return "high"
    if strong_count == 3:
        return "medium"
    if strong_count == 2:
        return "low"
    return "single_source" if contributors else "none"


def classify_rollup_overlap(contributors: list[dict[str, Any]]) -> str:
    expert_count = len({item["expert_id"] for item in contributors})
    exact_cell_count = len({item["matrix_cell_id"] for item in contributors})
    if exact_cell_count > 1 and expert_count > 1:
        return "related_multi_source"
    if exact_cell_count == 1 and expert_count > 1:
        return "exact_multi_source"
    if exact_cell_count > 1 and expert_count == 1:
        return "single_expert_multi_cell"
    return "single_source" if expert_count else "none"


def rollup_decision_hint(overlap_status: str, coverage_status: str) -> str:
    if overlap_status == "related_multi_source":
        if coverage_status == "strong_multi_source":
            return "review_overlap_or_complement_before_counting_as_new_gap"
        return "review_related_cells_before_counting_as_new_gap"
    if overlap_status == "exact_multi_source":
        return "possible_redundancy_in_exact_cell"
    if overlap_status == "single_expert_multi_cell":
        return "broad_single_expert_area"
    return "single_source_gap_or_specialization"


def iter_rollup_keys(contributor: dict[str, Any]) -> list[tuple[str, str]]:
    domain_id = contributor.get("domain_id") or "unknown_domain"
    query_intent_ids = contributor.get("query_intent_ids") or ["unknown_query_intent"]
    keys = [("domain", domain_id)]
    for query_intent_id in query_intent_ids:
        keys.append(("domain_query_intent", f"{domain_id}/{query_intent_id}"))
        keys.append(("query_intent", query_intent_id))
    return keys


def build_rollup(kind: str, rollup_id: str, contributors: list[dict[str, Any]]) -> dict[str, Any]:
    representative = contributors[0]
    expert_level_contributors = best_contributors_by_expert(contributors)
    exact_cell_ids = sorted({item["matrix_cell_id"] for item in contributors})
    subdomain_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in contributors:
        subdomain_groups[item.get("subdomain_id") or "unknown_subdomain"].append(item)

    overlap_status = classify_rollup_overlap(contributors)
    coverage_status = classify_coverage(expert_level_contributors)
    payload: dict[str, Any] = {
        "rollup_id": rollup_id,
        "rollup_kind": kind,
        "coverage_status": coverage_status,
        "redundancy_level": classify_redundancy(expert_level_contributors),
        "overlap_status": overlap_status,
        "decision_hint": rollup_decision_hint(overlap_status, coverage_status),
        "expert_count": len({item["expert_id"] for item in contributors}),
        "contribution_count": len(contributors),
        "exact_cell_count": len(exact_cell_ids),
        "exact_cell_ids": exact_cell_ids,
        "best_experts": best_experts_payload(expert_level_contributors),
        "score_summary": score_summary_payload(expert_level_contributors),
        "subdomains": [
            {
                "subdomain_id": subdomain_id,
                "subdomain_name": items[0].get("subdomain_name"),
                "expert_ids": sorted({item["expert_id"] for item in items}),
                "exact_cell_ids": sorted({item["matrix_cell_id"] for item in items}),
            }
            for subdomain_id, items in sorted(subdomain_groups.items())
        ],
    }
    if kind == "domain":
        payload["domain_id"] = rollup_id
    elif kind == "domain_query_intent":
        domain_id, query_intent_id = rollup_id.split("/", 1)
        payload["domain_id"] = domain_id
        payload["query_intent_id"] = query_intent_id
    elif kind == "query_intent":
        payload["query_intent_id"] = rollup_id
        payload["domain_ids"] = sorted({item.get("domain_id") for item in contributors if item.get("domain_id")})
    else:
        payload["representative_domain_id"] = representative.get("domain_id")
    return payload


def build_rollups(cells_payload: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        kind: defaultdict(list) for kind in ROLLUP_KINDS
    }
    for cell in cells_payload:
        for contributor in cell["contributors"]:
            for kind, rollup_id in iter_rollup_keys(contributor):
                grouped[kind][rollup_id].append(contributor)

    return {
        kind: [
            build_rollup(kind, rollup_id, contributors)
            for rollup_id, contributors in sorted(grouped[kind].items())
        ]
        for kind in ROLLUP_KINDS
    }


def taxonomy_flags(cell: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    domain_id = cell.get("domain_id")
    subdomain_id = cell.get("subdomain_id")
    query_intents = cell.get("query_intent_ids") or []

    if domain_id not in CORE_DOMAIN_IDS:
        flags.append(
            {
                "kind": "domain",
                "value": domain_id,
                "status": "proposed_extension",
                "alias_candidate": DOMAIN_ALIASES.get(domain_id),
                "cell_id": cell.get("cell_id"),
            }
        )
    if subdomain_id not in CORE_SUBDOMAIN_IDS:
        flags.append(
            {
                "kind": "subdomain",
                "value": subdomain_id,
                "status": "proposed_extension",
                "alias_candidate": SUBDOMAIN_ALIASES.get(subdomain_id),
                "cell_id": cell.get("cell_id"),
            }
        )
    for query_intent_id in query_intents:
        if query_intent_id not in CORE_QUERY_INTENT_IDS:
            flags.append(
                {
                    "kind": "query_intent",
                    "value": query_intent_id,
                    "status": "proposed_extension",
                    "alias_candidate": None,
                    "cell_id": cell.get("cell_id"),
                }
            )
    return flags


def build_matrix(passport_paths: list[Path]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    passports: list[dict[str, Any]] = []
    taxonomy_extensions: list[dict[str, Any]] = []
    applied_aliases: list[dict[str, Any]] = []

    for path in passport_paths:
        passport = read_json(path)
        meta = passport.get("passport_meta") or {}
        expert_id = meta.get("expert_id") or path.parent.parent.name
        display_name = meta.get("display_name", expert_id)
        cells = (passport.get("matrix_export") or {}).get("cells") or []
        passports.append(
            {
                "expert_id": expert_id,
                "display_name": display_name,
                "path": str(path),
                "cell_count": len(cells),
            }
        )

        for raw_cell in cells:
            cell, aliases = normalize_cell(raw_cell)
            applied_aliases.extend(
                {**alias, "expert_id": expert_id}
                for alias in aliases
            )
            key = cell_key(cell)
            contributor = {
                "expert_id": expert_id,
                "display_name": display_name,
                "passport_path": str(path),
                "matrix_cell_id": key,
                "cell_id": cell.get("cell_id", key),
                "original_cell_id": cell.get("original_cell_id"),
                "domain_id": cell.get("domain_id"),
                "subdomain_id": cell.get("subdomain_id"),
                "subdomain_name": cell.get("subdomain_name"),
                "query_intent_ids": cell.get("query_intent_ids", []),
                "source_role": cell.get("source_role", "unknown"),
                "coverage_level": cell.get("coverage_level"),
                "depth_level": cell.get("depth_level"),
                "scores": cell.get("scores") or {},
                "matrix_update_role": cell.get("matrix_update_role"),
                "limitations": cell.get("limitations", []),
                "evidence_refs": cell.get("evidence_refs", []),
                "confidence": cell.get("confidence"),
            }
            contributor["aggregate_score"] = score_contributor(contributor)
            grouped[key].append(contributor)
            taxonomy_extensions.extend(taxonomy_flags(cell))

    cells_payload: list[dict[str, Any]] = []
    for key, contributors in sorted(grouped.items()):
        cells_payload.append(
            {
                "matrix_cell_id": key,
                "domain_id": contributors[0]["domain_id"],
                "subdomain_id": contributors[0]["subdomain_id"],
                "subdomain_name": contributors[0]["subdomain_name"],
                "query_intent_ids": contributors[0]["query_intent_ids"],
                "coverage_status": classify_coverage(contributors),
                "redundancy_level": classify_redundancy(contributors),
                "expert_count": len(contributors),
                "best_experts": best_experts_payload(contributors),
                "score_summary": score_summary_payload(contributors),
                "contributors": contributors,
            }
        )

    unique_extensions = {
        (item["kind"], item["value"], item["cell_id"]): item
        for item in taxonomy_extensions
        if item["value"]
    }
    proposed_extensions = sorted(
        unique_extensions.values(),
        key=lambda item: (item["kind"], item["value"], item["cell_id"]),
    )
    rollups = build_rollups(cells_payload)
    related_cell_overlaps = [
        {
            "rollup_id": item["rollup_id"],
            "domain_id": item.get("domain_id"),
            "query_intent_id": item.get("query_intent_id"),
            "coverage_status": item["coverage_status"],
            "expert_count": item["expert_count"],
            "exact_cell_count": item["exact_cell_count"],
            "exact_cell_ids": item["exact_cell_ids"],
            "best_experts": item["best_experts"],
            "decision_hint": item["decision_hint"],
            "subdomains": item["subdomains"],
        }
        for item in rollups["domain_query_intent"]
        if item["overlap_status"] == "related_multi_source"
    ]

    return {
        "schema_version": "knowledge_matrix.v0.3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_passports": passports,
        "summary": {
            "passport_count": len(passports),
            "expert_count": len({item["expert_id"] for item in passports}),
            "matrix_cell_count": len(cells_payload),
            "taxonomy_extension_count": len(proposed_extensions),
            "strong_single_source_count": sum(
                1 for cell in cells_payload if cell["coverage_status"] == "strong_single_source"
            ),
            "strong_multi_source_count": sum(
                1 for cell in cells_payload if cell["coverage_status"] == "strong_multi_source"
            ),
            "single_source_cell_count": sum(
                1 for cell in cells_payload if cell["redundancy_level"] == "single_source"
            ),
            "applied_alias_count": len(applied_aliases),
            "domain_rollup_count": len(rollups["domain"]),
            "domain_query_intent_rollup_count": len(rollups["domain_query_intent"]),
            "query_intent_rollup_count": len(rollups["query_intent"]),
            "related_cell_overlap_count": len(related_cell_overlaps),
            "strong_domain_intent_multi_source_count": sum(
                1
                for item in rollups["domain_query_intent"]
                if item["coverage_status"] == "strong_multi_source"
            ),
        },
        "cells": cells_payload,
        "rollups": rollups,
        "related_cell_overlaps": related_cell_overlaps,
        "taxonomy_review": {
            "core_domain_ids": sorted(CORE_DOMAIN_IDS),
            "core_subdomain_ids": sorted(CORE_SUBDOMAIN_IDS),
            "core_query_intent_ids": sorted(CORE_QUERY_INTENT_IDS),
            "decisions": TAXONOMY_DECISIONS,
            "applied_aliases": applied_aliases,
            "proposed_extensions": proposed_extensions,
        },
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Knowledge Matrix v0.3",
        "",
        f"Generated: {matrix['created_at']}",
        "",
        "## Summary",
        "",
        f"- Passports: {matrix['summary']['passport_count']}",
        f"- Experts: {matrix['summary']['expert_count']}",
        f"- Matrix cells: {matrix['summary']['matrix_cell_count']}",
        f"- Taxonomy extensions: {matrix['summary']['taxonomy_extension_count']}",
        f"- Strong single-source cells: {matrix['summary']['strong_single_source_count']}",
        f"- Strong multi-source cells: {matrix['summary']['strong_multi_source_count']}",
        f"- Applied aliases: {matrix['summary']['applied_alias_count']}",
        f"- Domain + intent rollups: {matrix['summary']['domain_query_intent_rollup_count']}",
        f"- Related cell overlaps: {matrix['summary']['related_cell_overlap_count']}",
        (
            "- Strong domain + intent multi-source rollups: "
            f"{matrix['summary']['strong_domain_intent_multi_source_count']}"
        ),
        "",
        "## Cells",
        "",
        "| Cell | Coverage | Redundancy | Best experts | Scores |",
        "|------|----------|------------|--------------|--------|",
    ]

    for cell in matrix["cells"]:
        best = ", ".join(
            f"{item['display_name']} ({item['source_role']}, {item['aggregate_score']})"
            for item in cell["best_experts"]
        )
        scores = ", ".join(
            f"{key}: {value['max']}"
            for key, value in cell["score_summary"].items()
            if key in {"depth", "practicality", "evidence_quality", "source_utility"}
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{cell['matrix_cell_id']}`",
                    cell["coverage_status"],
                    cell["redundancy_level"],
                    best,
                    scores,
                ]
            )
            + " |"
        )

    lines.extend(["", "## Domain + Intent Rollups", ""])
    domain_intent_rollups = matrix.get("rollups", {}).get("domain_query_intent", [])
    if not domain_intent_rollups:
        lines.append("No domain + intent rollups.")
    else:
        lines.extend(
            [
                "| Rollup | Coverage | Overlap | Experts | Cells | Decision hint |",
                "|--------|----------|---------|---------|-------|---------------|",
            ]
        )
        for item in domain_intent_rollups:
            best = ", ".join(
                f"{expert['display_name']} ({expert['source_role']}, {expert['aggregate_score']})"
                for expert in item["best_experts"]
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{item['rollup_id']}`",
                        item["coverage_status"],
                        item["overlap_status"],
                        best,
                        str(item["exact_cell_count"]),
                        item["decision_hint"],
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Related Cell Overlaps", ""])
    related_overlaps = matrix.get("related_cell_overlaps", [])
    if not related_overlaps:
        lines.append("No related cell overlaps.")
    else:
        lines.extend(
            [
                "| Rollup | Experts | Related cells | Decision hint |",
                "|--------|---------|---------------|---------------|",
            ]
        )
        for item in related_overlaps:
            best = ", ".join(expert["display_name"] for expert in item["best_experts"])
            cells = "<br>".join(f"`{cell_id}`" for cell_id in item["exact_cell_ids"])
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{item['rollup_id']}`",
                        best,
                        cells,
                        item["decision_hint"],
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Taxonomy Decisions", ""])
    lines.extend(
        [
            "| Kind | Value | Decision | Rationale |",
            "|------|-------|----------|-----------|",
        ]
    )
    for item in matrix["taxonomy_review"]["decisions"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["kind"],
                    f"`{item['value']}`",
                    item["decision"],
                    item["rationale"],
                ]
            )
            + " |"
        )

    lines.extend(["", "## Applied Aliases", ""])
    applied_aliases = matrix["taxonomy_review"]["applied_aliases"]
    if not applied_aliases:
        lines.append("No aliases applied.")
    else:
        lines.extend(
            [
                "| Kind | From | To | Expert | Cell |",
                "|------|------|----|--------|------|",
            ]
        )
        for item in applied_aliases:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item["kind"],
                        f"`{item['from']}`",
                        f"`{item['to']}`",
                        f"`{item['expert_id']}`",
                        f"`{item['cell_id']}`",
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Taxonomy Review", ""])
    proposed = matrix["taxonomy_review"]["proposed_extensions"]
    if not proposed:
        lines.append("No proposed extensions.")
    else:
        lines.extend(
            [
                "| Kind | Value | Alias candidate | Cell |",
                "|------|-------|-----------------|------|",
            ]
        )
        for item in proposed:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item["kind"],
                        f"`{item['value']}`",
                        f"`{item['alias_candidate']}`" if item["alias_candidate"] else "",
                        f"`{item['cell_id']}`",
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Source Passports", ""])
    for passport in matrix["source_passports"]:
        lines.append(
            f"- `{passport['expert_id']}`: {passport['display_name']} "
            f"({passport['cell_count']} cells) — `{passport['path']}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build knowledge matrix from normalized passports.")
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--admission-manifest",
        type=Path,
        default=DEFAULT_ADMISSION_MANIFEST,
        help="Admission manifest used to select accepted passports by default.",
    )
    parser.add_argument(
        "--include-all-passports",
        action="store_true",
        help="Ignore the admission manifest and build from every normalized passport under input root.",
    )
    parser.add_argument(
        "passports",
        nargs="*",
        type=Path,
        help="Optional explicit normalized passport paths. Overrides the admission manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    passport_paths = select_passports(
        input_root=args.input_root,
        explicit_passports=args.passports,
        admission_manifest_path=args.admission_manifest,
        include_all_passports=args.include_all_passports,
    )
    if not passport_paths:
        raise SystemExit(f"No normalized passports found under {args.input_root}")

    matrix = build_matrix(passport_paths)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "knowledge_matrix.json", matrix)
    (args.out_dir / "knowledge_matrix.md").write_text(render_markdown(matrix), encoding="utf-8")
    print(f"Wrote {args.out_dir / 'knowledge_matrix.json'}")
    print(f"Wrote {args.out_dir / 'knowledge_matrix.md'}")
    print(json.dumps(matrix["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
