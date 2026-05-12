#!/usr/bin/env python3
"""Evaluate one semantic passport against the current knowledge matrix.

This is a deterministic diagnostic preflight. It does not call Vertex AI and it
does not mutate the production database. The expensive semantic work is assumed
to be done already in the candidate's normalized semantic passport.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_knowledge_matrix as matrix_builder  # noqa: E402


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_INPUT_ROOT = REPO_ROOT / "output" / "expert_admission" / "semantic_passports"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "expert_admission" / "candidates"
DEFAULT_ADMISSION_MANIFEST = matrix_builder.DEFAULT_ADMISSION_MANIFEST

POSITIVE_CLASSIFICATIONS = {
    "fills_gap",
    "adds_adjacent_viewpoint",
    "deepens_existing_cell",
}
DENSE_ROLLUP_EXPERT_THRESHOLD = 3

REPORT_SCHEMA_VERSION = "candidate_impact_report.v0.1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def passport_meta(passport: dict[str, Any], path: Path) -> dict[str, Any]:
    meta = passport.get("passport_meta") or {}
    expert_id = meta.get("expert_id") or path.parent.parent.name
    return {
        "expert_id": expert_id,
        "display_name": meta.get("display_name", expert_id),
        "channel_username": meta.get("channel_username"),
        "schema_version": meta.get("schema_version"),
        "generated_at": meta.get("generated_at"),
        "passport_path": str(path),
    }


def candidate_contributors(passport: dict[str, Any], meta: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contributors: list[dict[str, Any]] = []
    applied_aliases: list[dict[str, Any]] = []
    taxonomy_flags: list[dict[str, Any]] = []

    cells = (passport.get("matrix_export") or {}).get("cells") or []
    for raw_cell in cells:
        cell, aliases = matrix_builder.normalize_cell(raw_cell)
        applied_aliases.extend({**alias, "expert_id": meta["expert_id"]} for alias in aliases)
        taxonomy_flags.extend(matrix_builder.taxonomy_flags(cell))
        matrix_cell_id = matrix_builder.cell_key(cell)
        contributor = {
            "expert_id": meta["expert_id"],
            "display_name": meta["display_name"],
            "passport_path": meta["passport_path"],
            "matrix_cell_id": matrix_cell_id,
            "cell_id": cell.get("cell_id", matrix_cell_id),
            "original_cell_id": cell.get("original_cell_id"),
            "domain_id": cell.get("domain_id"),
            "subdomain_id": cell.get("subdomain_id"),
            "subdomain_name": cell.get("subdomain_name"),
            "query_intent_ids": cell.get("query_intent_ids") or [],
            "source_role": cell.get("source_role", "unknown"),
            "coverage_level": cell.get("coverage_level"),
            "depth_level": cell.get("depth_level"),
            "scores": cell.get("scores") or {},
            "matrix_update_role": cell.get("matrix_update_role"),
            "limitations": cell.get("limitations", []),
            "evidence_refs": cell.get("evidence_refs", []),
            "confidence": cell.get("confidence"),
        }
        contributor["aggregate_score"] = matrix_builder.score_contributor(contributor)
        contributors.append(contributor)

    unique_flags = {
        (item["kind"], item["value"], item["cell_id"]): item
        for item in taxonomy_flags
        if item["value"]
    }
    return contributors, applied_aliases, sorted(unique_flags.values(), key=lambda item: (item["kind"], item["value"], item["cell_id"]))


def discover_baseline_passports(
    input_root: Path,
    candidate_path: Path,
    candidate_expert_id: str,
    explicit_baseline_paths: list[Path],
    include_candidate_in_baseline: bool,
    admission_manifest_path: Path | None = DEFAULT_ADMISSION_MANIFEST,
    include_all_baseline_passports: bool = False,
) -> list[Path]:
    if explicit_baseline_paths:
        paths = explicit_baseline_paths
    else:
        paths = matrix_builder.select_passports(
            input_root=input_root,
            admission_manifest_path=admission_manifest_path,
            include_all_passports=include_all_baseline_passports,
        )

    candidate_resolved = candidate_path.resolve()
    baseline_paths: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if not include_candidate_in_baseline and resolved == candidate_resolved:
            continue
        if not include_candidate_in_baseline:
            try:
                expert_id = passport_meta(read_json(path), path)["expert_id"]
            except (OSError, json.JSONDecodeError):
                expert_id = None
            if expert_id == candidate_expert_id:
                continue
        baseline_paths.append(path)
    return baseline_paths


def exact_cells_by_id(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["matrix_cell_id"]: item for item in matrix.get("cells", [])}


def domain_intent_rollups_by_id(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["rollup_id"]: item
        for item in matrix.get("rollups", {}).get("domain_query_intent", [])
    }


def taxonomy_flags_for_contributor(contributor: dict[str, Any], all_flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_ids = {contributor["matrix_cell_id"], contributor.get("cell_id")}
    return [item for item in all_flags if item.get("cell_id") in candidate_ids]


def domain_intent_matches(contributor: dict[str, Any], baseline_rollups: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    domain_id = contributor.get("domain_id") or "unknown_domain"
    for query_intent_id in contributor.get("query_intent_ids") or ["unknown_query_intent"]:
        rollup_id = f"{domain_id}/{query_intent_id}"
        rollup = baseline_rollups.get(rollup_id)
        if not rollup:
            continue
        matches.append(
            {
                "rollup_id": rollup_id,
                "coverage_status": rollup["coverage_status"],
                "overlap_status": rollup["overlap_status"],
                "expert_count": rollup["expert_count"],
                "exact_cell_count": rollup["exact_cell_count"],
                "exact_cell_ids": rollup["exact_cell_ids"],
                "best_experts": rollup["best_experts"],
            }
        )
    return matches


def is_dense_exact_match(exact_match: dict[str, Any] | None) -> bool:
    if not exact_match:
        return False
    return (
        exact_match.get("coverage_status") == "strong_multi_source"
        or exact_match.get("redundancy_level") in {"medium", "high"}
        or exact_match.get("expert_count", 0) >= DENSE_ROLLUP_EXPERT_THRESHOLD
    )


def is_dense_rollup_match(match: dict[str, Any]) -> bool:
    return (
        match.get("coverage_status") == "strong_multi_source"
        or match.get("overlap_status") in {"exact_multi_source", "related_multi_source"}
        or match.get("expert_count", 0) >= DENSE_ROLLUP_EXPERT_THRESHOLD
    )


def has_dense_overlap(impact: dict[str, Any]) -> bool:
    if is_dense_exact_match(impact.get("exact_match")):
        return True
    return any(is_dense_rollup_match(match) for match in impact.get("domain_query_intent_matches") or [])


def density_summary(cell_impacts: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    total = summary["candidate_cell_count"]
    overlap_impacts = [
        item
        for item in cell_impacts
        if item.get("exact_match") or item.get("domain_query_intent_matches")
    ]
    positive_overlap_impacts = [
        item for item in overlap_impacts if item["classification"] in POSITIVE_CLASSIFICATIONS
    ]
    dense_overlap_impacts = [item for item in overlap_impacts if has_dense_overlap(item)]
    dense_positive_overlap_impacts = [
        item for item in positive_overlap_impacts if has_dense_overlap(item)
    ]
    clean_gap_impacts = [
        item
        for item in cell_impacts
        if item["classification"] == "fills_gap"
        and not item.get("exact_match")
        and not item.get("domain_query_intent_matches")
    ]

    overlap_cell_count = len(overlap_impacts)
    positive_overlap_cell_count = len(positive_overlap_impacts)
    dense_overlap_cell_count = len(dense_overlap_impacts)
    overlap_cell_share = round(overlap_cell_count / total, 3) if total else 0
    density_caveat = (
        total > 0
        and overlap_cell_share >= 0.5
        and dense_overlap_cell_count >= 2
        and (
            summary["likely_duplicate_count"] > 0
            or positive_overlap_cell_count >= 2
        )
    )

    reasons: list[str] = []
    if density_caveat:
        reasons.append("At least half of candidate cells overlap existing accepted coverage.")
        reasons.append("Two or more candidate cells touch dense accepted rollups or exact cells.")
        if summary["likely_duplicate_count"] > 0:
            reasons.append("At least one candidate cell is an exact likely duplicate.")
        if positive_overlap_cell_count >= 2:
            reasons.append("Multiple positive signals are adjacent/depth signals rather than clean gaps.")

    return {
        "overlap_cell_count": overlap_cell_count,
        "overlap_cell_share": overlap_cell_share,
        "positive_overlap_cell_count": positive_overlap_cell_count,
        "dense_overlap_cell_count": dense_overlap_cell_count,
        "dense_positive_overlap_cell_count": len(dense_positive_overlap_impacts),
        "clean_gap_count": len(clean_gap_impacts),
        "density_caveat": density_caveat,
        "density_caveat_reasons": reasons,
    }


def normalize_confidence_0_5(confidence: Any) -> float | None:
    if confidence is None:
        return None
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    if value <= 1:
        return round(value * 5, 3)
    return value


def classify_cell_impact(
    contributor: dict[str, Any],
    exact_match: dict[str, Any] | None,
    rollup_matches: list[dict[str, Any]],
    flags: list[dict[str, Any]],
) -> tuple[str, str, str]:
    score = contributor["aggregate_score"]
    source_role = contributor.get("source_role")
    confidence = normalize_confidence_0_5(contributor.get("confidence"))
    evidence_ref_count = len(contributor.get("evidence_refs") or [])

    if source_role in {"weak", "avoid"} or score < 3.3:
        return (
            "noise_risk",
            "Candidate cell has weak source role or low aggregate score.",
            "reject_cell_or_probe_only_if_strategic",
        )

    if confidence is not None and confidence < 3:
        return (
            "needs_probe",
            "Candidate cell has low confidence in the semantic passport.",
            "run_deeper_candidate_probe",
        )

    if evidence_ref_count == 0:
        return (
            "needs_probe",
            "Candidate cell has no cited evidence refs.",
            "run_source_level_probe",
        )

    if flags:
        return (
            "taxonomy_extension",
            "Candidate cell uses taxonomy values outside the current core taxonomy.",
            "taxonomy_review",
        )

    if exact_match:
        best_existing_score = max(
            (item["aggregate_score"] for item in exact_match.get("contributors", [])),
            default=0,
        )
        existing_coverage = exact_match.get("coverage_status")
        if existing_coverage in {"thin", "moderate"} or score >= best_existing_score + 0.25:
            return (
                "deepens_existing_cell",
                "Candidate overlaps an exact cell but improves a thin/moderate or weaker baseline.",
                "human_review_then_possible_accept",
            )
        return (
            "likely_duplicate",
            "Candidate maps to an already-covered exact cell without a clear deterministic score lift.",
            "check_representative_posts_before_counting_as_unique",
        )

    if rollup_matches:
        if source_role == "primary" and score >= 4.0:
            return (
                "adds_adjacent_viewpoint",
                "Candidate adds a new exact cell inside an already-covered domain + query intent area.",
                "human_review_overlap_or_complement",
            )
        return (
            "needs_probe",
            "Candidate is adjacent to existing coverage but not strong enough for automatic positive impact.",
            "run_deeper_candidate_probe",
        )

    if source_role == "primary" and score >= 4.0:
        return (
            "fills_gap",
            "Candidate creates a strong new exact cell outside the current baseline rollups.",
            "human_review_then_possible_accept",
        )
    return (
        "needs_probe",
        "Candidate creates a new area, but deterministic strength is not high enough.",
        "run_deeper_candidate_probe",
    )


def closest_existing_experts(cell_impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for impact in cell_impacts:
        seen_in_cell: set[str] = set()
        pools: list[tuple[str, list[dict[str, Any]]]] = []
        exact = impact.get("exact_match")
        if exact:
            pools.append(("exact_cell", exact.get("best_experts") or []))
        for match in impact.get("domain_query_intent_matches") or []:
            pools.append(("domain_query_intent", match.get("best_experts") or []))

        for match_type, experts in pools:
            for expert in experts:
                expert_id = expert["expert_id"]
                key = f"{impact['candidate_cell_id']}:{match_type}:{expert_id}"
                if key in seen_in_cell:
                    continue
                seen_in_cell.add(key)
                item = stats.setdefault(
                    expert_id,
                    {
                        "expert_id": expert_id,
                        "display_name": expert["display_name"],
                        "match_count": 0,
                        "exact_match_count": 0,
                        "related_match_count": 0,
                        "matched_candidate_cells": set(),
                        "matched_rollups": set(),
                        "best_existing_score": expert.get("aggregate_score") or 0,
                    },
                )
                item["match_count"] += 1
                if match_type == "exact_cell":
                    item["exact_match_count"] += 1
                else:
                    item["related_match_count"] += 1
                item["matched_candidate_cells"].add(impact["candidate_cell_id"])
                for match in impact.get("domain_query_intent_matches") or []:
                    item["matched_rollups"].add(match["rollup_id"])
                item["best_existing_score"] = max(
                    item["best_existing_score"],
                    expert.get("aggregate_score") or 0,
                )

    return [
        {
            **item,
            "matched_candidate_cells": sorted(item["matched_candidate_cells"]),
            "matched_rollups": sorted(item["matched_rollups"]),
        }
        for item in sorted(
            stats.values(),
            key=lambda item: (item["match_count"], item["best_existing_score"]),
            reverse=True,
        )
    ]


def preliminary_recommendation(summary: dict[str, Any]) -> str:
    positive = sum(summary[f"{name}_count"] for name in POSITIVE_CLASSIFICATIONS)
    duplicate = summary["likely_duplicate_count"]
    probe = summary["needs_probe_count"]
    taxonomy = summary["taxonomy_extension_count"]
    noise = summary["noise_risk_count"]
    total = summary["candidate_cell_count"]

    if total == 0:
        return "insufficient_passport_data"
    if (
        summary.get("density_caveat")
        and positive >= 1
        and noise == 0
    ):
        return "overlap_heavy_needs_stronger_review"
    if positive >= 2 and duplicate <= positive and noise == 0:
        return "promising_needs_human_review"
    if positive >= 1 and (probe > 0 or taxonomy > 0):
        return "promising_but_probe_or_taxonomy_review"
    if duplicate == total:
        return "likely_duplicate_or_low_increment"
    if taxonomy > 0:
        return "taxonomy_review_needed"
    if noise > 0 and positive == 0:
        return "weak_or_noisy"
    return "probe_needed"


def build_candidate_report(candidate_passport_path: Path, baseline_passport_paths: list[Path]) -> dict[str, Any]:
    candidate_passport = read_json(candidate_passport_path)
    meta = passport_meta(candidate_passport, candidate_passport_path)
    contributors, applied_aliases, taxonomy_flags = candidate_contributors(candidate_passport, meta)
    baseline_matrix = matrix_builder.build_matrix(baseline_passport_paths)
    baseline_cells = exact_cells_by_id(baseline_matrix)
    baseline_rollups = domain_intent_rollups_by_id(baseline_matrix)

    cell_impacts: list[dict[str, Any]] = []
    for contributor in contributors:
        exact_match = baseline_cells.get(contributor["matrix_cell_id"])
        rollup_matches = domain_intent_matches(contributor, baseline_rollups)
        flags = taxonomy_flags_for_contributor(contributor, taxonomy_flags)
        classification, rationale, next_action = classify_cell_impact(
            contributor,
            exact_match,
            rollup_matches,
            flags,
        )
        cell_impacts.append(
            {
                "candidate_cell_id": contributor["matrix_cell_id"],
                "candidate_original_cell_id": contributor.get("original_cell_id"),
                "classification": classification,
                "rationale": rationale,
                "suggested_next_action": next_action,
                "domain_id": contributor.get("domain_id"),
                "subdomain_id": contributor.get("subdomain_id"),
                "subdomain_name": contributor.get("subdomain_name"),
                "query_intent_ids": contributor.get("query_intent_ids"),
                "source_role": contributor.get("source_role"),
                "coverage_level": contributor.get("coverage_level"),
                "depth_level": contributor.get("depth_level"),
                "aggregate_score": contributor["aggregate_score"],
                "scores": contributor.get("scores"),
                "confidence": contributor.get("confidence"),
                "confidence_normalized_0_5": normalize_confidence_0_5(contributor.get("confidence")),
                "evidence_ref_count": len(contributor.get("evidence_refs") or []),
                "limitations": contributor.get("limitations") or [],
                "taxonomy_flags": flags,
                "exact_match": exact_match
                and {
                    "matrix_cell_id": exact_match["matrix_cell_id"],
                    "coverage_status": exact_match["coverage_status"],
                    "redundancy_level": exact_match["redundancy_level"],
                    "expert_count": exact_match["expert_count"],
                    "best_experts": exact_match["best_experts"],
                },
                "domain_query_intent_matches": rollup_matches,
            }
        )

    summary = {
        "candidate_cell_count": len(cell_impacts),
        "fills_gap_count": sum(1 for item in cell_impacts if item["classification"] == "fills_gap"),
        "adds_adjacent_viewpoint_count": sum(
            1 for item in cell_impacts if item["classification"] == "adds_adjacent_viewpoint"
        ),
        "deepens_existing_cell_count": sum(
            1 for item in cell_impacts if item["classification"] == "deepens_existing_cell"
        ),
        "likely_duplicate_count": sum(1 for item in cell_impacts if item["classification"] == "likely_duplicate"),
        "taxonomy_extension_count": sum(1 for item in cell_impacts if item["classification"] == "taxonomy_extension"),
        "needs_probe_count": sum(1 for item in cell_impacts if item["classification"] == "needs_probe"),
        "noise_risk_count": sum(1 for item in cell_impacts if item["classification"] == "noise_risk"),
        "exact_overlap_count": sum(1 for item in cell_impacts if item["exact_match"]),
        "related_overlap_count": sum(
            1
            for item in cell_impacts
            if item["domain_query_intent_matches"] and not item["exact_match"]
        ),
    }
    summary["positive_impact_count"] = sum(
        summary[f"{name}_count"] for name in POSITIVE_CLASSIFICATIONS
    )
    summary.update(density_summary(cell_impacts, summary))
    summary["preliminary_recommendation"] = preliminary_recommendation(summary)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_mode": "semantic_matrix_preflight",
        "admission_verdict": "not_assessed",
        "candidate": {
            **meta,
            "cell_count": len(contributors),
        },
        "baseline": {
            "passport_paths": [str(path) for path in baseline_passport_paths],
            "summary": baseline_matrix["summary"],
            "source_passports": baseline_matrix["source_passports"],
        },
        "summary": summary,
        "cell_impacts": cell_impacts,
        "closest_existing_experts": closest_existing_experts(cell_impacts),
        "candidate_applied_aliases": applied_aliases,
        "candidate_taxonomy_flags": taxonomy_flags,
        "limitations": [
            "Diagnostic-only report; it does not make a final admission decision.",
            "Comparison is deterministic over passport matrix_export cells and matrix rollups.",
            "It does not inspect raw posts, runtime retrieval behavior, embeddings, or source_bundle quality.",
            "LLM arbitration is still useful for borderline duplicate-vs-complement cases.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    candidate = report["candidate"]
    summary = report["summary"]
    lines = [
        f"# Candidate Impact Report: {candidate['display_name']}",
        "",
        "## Preliminary Recommendation",
        "",
        f"- Recommendation: `{summary['preliminary_recommendation']}`",
        f"- Admission verdict: `{report['admission_verdict']}`",
        f"- Evaluation mode: `{report['evaluation_mode']}`",
        "",
        "This is a deterministic preflight report, not a final admission decision.",
        "",
        "## Candidate Data",
        "",
        f"- Expert ID: `{candidate['expert_id']}`",
        f"- Display name: {candidate['display_name']}",
        f"- Channel username: `{candidate.get('channel_username')}`",
        f"- Passport cells: {candidate['cell_count']}",
        f"- Passport: `{candidate['passport_path']}`",
        "",
        "## Baseline",
        "",
        f"- Baseline passports: {report['baseline']['summary']['passport_count']}",
        f"- Baseline experts: {report['baseline']['summary']['expert_count']}",
        f"- Baseline exact cells: {report['baseline']['summary']['matrix_cell_count']}",
        f"- Baseline domain + intent rollups: {report['baseline']['summary'].get('domain_query_intent_rollup_count', 0)}",
        "",
        "## Impact Summary",
        "",
        f"- Candidate cells: {summary['candidate_cell_count']}",
        f"- Fills gap: {summary['fills_gap_count']}",
        f"- Adds adjacent viewpoint: {summary['adds_adjacent_viewpoint_count']}",
        f"- Deepens existing cell: {summary['deepens_existing_cell_count']}",
        f"- Likely duplicate: {summary['likely_duplicate_count']}",
        f"- Taxonomy extension: {summary['taxonomy_extension_count']}",
        f"- Needs probe: {summary['needs_probe_count']}",
        f"- Noise risk: {summary['noise_risk_count']}",
        f"- Exact overlaps: {summary['exact_overlap_count']}",
        f"- Related overlaps: {summary['related_overlap_count']}",
        f"- Overlap-heavy caveat: {summary.get('density_caveat', False)}",
        f"- Clean gaps outside accepted overlap: {summary.get('clean_gap_count', 0)}",
        f"- Dense overlap cells: {summary.get('dense_overlap_cell_count', 0)}",
        "",
        "## Cell Impacts",
        "",
        "| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |",
        "|----------------|----------------|-------|-------------|-----------------|-------------|",
    ]

    for impact in report["cell_impacts"]:
        exact = impact["exact_match"]["matrix_cell_id"] if impact["exact_match"] else ""
        rollups = "<br>".join(
            f"`{item['rollup_id']}`" for item in impact["domain_query_intent_matches"]
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{impact['candidate_cell_id']}`",
                    impact["classification"],
                    str(impact["aggregate_score"]),
                    f"`{exact}`" if exact else "",
                    rollups,
                    impact["suggested_next_action"],
                ]
            )
            + " |"
        )

    lines.extend(["", "## Closest Existing Experts", ""])
    if not report["closest_existing_experts"]:
        lines.append("No exact or related existing experts found.")
    else:
        lines.extend(
            [
                "| Expert | Matches | Exact | Related | Rollups |",
                "|--------|---------|-------|---------|---------|",
            ]
        )
        for expert in report["closest_existing_experts"]:
            rollups = "<br>".join(f"`{item}`" for item in expert["matched_rollups"])
            lines.append(
                "| "
                + " | ".join(
                    [
                        expert["display_name"],
                        str(expert["match_count"]),
                        str(expert["exact_match_count"]),
                        str(expert["related_match_count"]),
                        rollups,
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Taxonomy Flags", ""])
    if not report["candidate_taxonomy_flags"]:
        lines.append("No candidate taxonomy extensions.")
    else:
        lines.extend(
            [
                "| Kind | Value | Cell |",
                "|------|-------|------|",
            ]
        )
        for item in report["candidate_taxonomy_flags"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item["kind"],
                        f"`{item['value']}`",
                        f"`{item['cell_id']}`",
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Limitations", ""])
    for item in report["limitations"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Next Action", ""])
    recommendation = summary["preliminary_recommendation"]
    if recommendation == "promising_needs_human_review":
        lines.append("Human review of overlap/complement signals, then continue with admission decision or targeted probe.")
    elif recommendation == "overlap_heavy_needs_stronger_review":
        lines.append("Candidate is promising but overlap-heavy; require stronger human review before admission.")
        reasons = summary.get("density_caveat_reasons") or []
        if reasons:
            lines.extend(["", "Density caveat:"])
            lines.extend(f"- {reason}" for reason in reasons)
    elif recommendation == "likely_duplicate_or_low_increment":
        lines.append("Review representative posts before spending on deeper probes.")
    elif recommendation == "taxonomy_review_needed":
        lines.append("Resolve taxonomy extension before comparing admission value.")
    else:
        lines.append("Run a deeper candidate probe only if the candidate is strategically important.")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate one semantic passport against a baseline knowledge matrix.")
    parser.add_argument("--candidate-passport", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument(
        "--admission-manifest",
        type=Path,
        default=DEFAULT_ADMISSION_MANIFEST,
        help="Admission manifest used to select accepted baseline passports by default.",
    )
    parser.add_argument(
        "--baseline-passport",
        type=Path,
        action="append",
        default=[],
        help="Explicit baseline passport path. May be repeated. Overrides the admission manifest.",
    )
    parser.add_argument(
        "--include-all-baseline-passports",
        action="store_true",
        help="Ignore the admission manifest and use every normalized passport under input root as baseline.",
    )
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument(
        "--include-candidate-in-baseline",
        action="store_true",
        help="Do not exclude same expert_id/candidate path from baseline. Mostly useful for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_passport = read_json(args.candidate_passport)
    meta = passport_meta(candidate_passport, args.candidate_passport)
    baseline_paths = discover_baseline_passports(
        args.input_root,
        args.candidate_passport,
        meta["expert_id"],
        args.baseline_passport,
        args.include_candidate_in_baseline,
        args.admission_manifest,
        args.include_all_baseline_passports,
    )
    report = build_candidate_report(args.candidate_passport, baseline_paths)

    out_dir = args.out_dir or DEFAULT_OUTPUT_ROOT / meta["expert_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "candidate_impact_report.json"
    md_path = out_dir / "candidate_impact_report.md"
    overlap_path = out_dir / "overlap_report.json"
    write_json(json_path, report)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    write_json(
        overlap_path,
        {
            "schema_version": "candidate_overlap_report.v0.1",
            "created_at": report["created_at"],
            "candidate": report["candidate"],
            "summary": {
                key: report["summary"][key]
                for key in (
                    "exact_overlap_count",
                    "related_overlap_count",
                    "likely_duplicate_count",
                    "adds_adjacent_viewpoint_count",
                    "deepens_existing_cell_count",
                )
            },
            "cell_impacts": [
                item
                for item in report["cell_impacts"]
                if item["exact_match"] or item["domain_query_intent_matches"]
            ],
            "closest_existing_experts": report["closest_existing_experts"],
        },
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {overlap_path}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
