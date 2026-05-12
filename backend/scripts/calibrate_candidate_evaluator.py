#!/usr/bin/env python3
"""Run leave-one-out calibration for the candidate impact evaluator.

Each existing normalized semantic passport is treated as a candidate while all
other passports form the baseline. This validates whether the deterministic
candidate evaluator behaves sensibly before using it on new experts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_knowledge_matrix as matrix_builder  # noqa: E402
import evaluate_expert_candidate as candidate_eval  # noqa: E402


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_INPUT_ROOT = REPO_ROOT / "output" / "expert_admission" / "semantic_passports"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "expert_admission" / "candidate_calibration"
DEFAULT_ADMISSION_MANIFEST = matrix_builder.DEFAULT_ADMISSION_MANIFEST

REPORT_SCHEMA_VERSION = "candidate_evaluator_calibration.v0.1"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def passport_identity(path: Path) -> dict[str, Any]:
    passport = candidate_eval.read_json(path)
    return candidate_eval.passport_meta(passport, path)


def baseline_paths_for_candidate(candidate_path: Path, candidate_expert_id: str, all_paths: list[Path]) -> list[Path]:
    candidate_resolved = candidate_path.resolve()
    baseline_paths: list[Path] = []
    for path in all_paths:
        if path.resolve() == candidate_resolved:
            continue
        meta = passport_identity(path)
        if meta["expert_id"] == candidate_expert_id:
            continue
        baseline_paths.append(path)
    return baseline_paths


def classification_counter(report: dict[str, Any]) -> Counter[str]:
    return Counter(item["classification"] for item in report["cell_impacts"])


def compact_case(report: dict[str, Any], baseline_paths: list[Path]) -> dict[str, Any]:
    candidate = report["candidate"]
    counts = classification_counter(report)
    baseline_experts = [
        item["expert_id"]
        for item in report["baseline"]["source_passports"]
    ]
    return {
        "candidate_expert_id": candidate["expert_id"],
        "candidate_display_name": candidate["display_name"],
        "candidate_passport_path": candidate["passport_path"],
        "baseline_passport_count": len(baseline_paths),
        "baseline_expert_ids": baseline_experts,
        "preliminary_recommendation": report["summary"]["preliminary_recommendation"],
        "candidate_cell_count": report["summary"]["candidate_cell_count"],
        "positive_impact_count": report["summary"]["positive_impact_count"],
        "classification_counts": dict(sorted(counts.items())),
        "exact_overlap_count": report["summary"]["exact_overlap_count"],
        "related_overlap_count": report["summary"]["related_overlap_count"],
        "closest_existing_experts": report["closest_existing_experts"],
        "cell_impacts": [
            {
                "candidate_cell_id": item["candidate_cell_id"],
                "classification": item["classification"],
                "aggregate_score": item["aggregate_score"],
                "source_role": item["source_role"],
                "exact_match": item["exact_match"]["matrix_cell_id"] if item["exact_match"] else None,
                "related_rollups": [
                    match["rollup_id"] for match in item["domain_query_intent_matches"]
                ],
                "suggested_next_action": item["suggested_next_action"],
            }
            for item in report["cell_impacts"]
        ],
    }


def aggregate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    classification_totals: Counter[str] = Counter()
    recommendation_totals: Counter[str] = Counter()
    for case in cases:
        classification_totals.update(case["classification_counts"])
        recommendation_totals.update([case["preliminary_recommendation"]])

    return {
        "case_count": len(cases),
        "total_candidate_cells": sum(case["candidate_cell_count"] for case in cases),
        "total_positive_impact": sum(case["positive_impact_count"] for case in cases),
        "total_exact_overlaps": sum(case["exact_overlap_count"] for case in cases),
        "total_related_overlaps": sum(case["related_overlap_count"] for case in cases),
        "classification_totals": dict(sorted(classification_totals.items())),
        "recommendation_totals": dict(sorted(recommendation_totals.items())),
        "cases_with_no_positive_impact": [
            case["candidate_expert_id"]
            for case in cases
            if case["positive_impact_count"] == 0
        ],
        "cases_with_duplicate_only_signal": [
            case["candidate_expert_id"]
            for case in cases
            if case["classification_counts"].get("likely_duplicate", 0) == case["candidate_cell_count"]
        ],
        "cases_with_probe_need": [
            case["candidate_expert_id"]
            for case in cases
            if case["classification_counts"].get("needs_probe", 0) > 0
        ],
    }


def build_calibration(passport_paths: list[Path]) -> dict[str, Any]:
    if len(passport_paths) < 2:
        raise ValueError("Leave-one-out calibration requires at least 2 passports.")

    cases: list[dict[str, Any]] = []
    detailed_reports: dict[str, dict[str, Any]] = {}
    sorted_paths = sorted(passport_paths)
    for candidate_path in sorted_paths:
        meta = passport_identity(candidate_path)
        baseline_paths = baseline_paths_for_candidate(candidate_path, meta["expert_id"], sorted_paths)
        report = candidate_eval.build_candidate_report(candidate_path, baseline_paths)
        cases.append(compact_case(report, baseline_paths))
        detailed_reports[meta["expert_id"]] = report

    aggregate = aggregate_cases(cases)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "calibration_mode": "leave_one_out",
        "input_passport_count": len(sorted_paths),
        "input_passports": [str(path) for path in sorted_paths],
        "aggregate": aggregate,
        "cases": sorted(cases, key=lambda item: item["candidate_expert_id"]),
        "calibration_interpretation": interpret_calibration(aggregate),
        "_detailed_reports": detailed_reports,
    }


def interpret_calibration(aggregate: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not aggregate["cases_with_no_positive_impact"]:
        notes.append("Every leave-one-out case produced at least one positive impact signal.")
    else:
        notes.append(
            "Some cases produced no positive impact and should be manually inspected before adding more experts."
        )

    if aggregate["cases_with_duplicate_only_signal"]:
        notes.append("At least one case looks duplicate-only under the current heuristics.")
    else:
        notes.append("No case is duplicate-only under the current heuristics.")

    if aggregate["total_related_overlaps"] > 0:
        notes.append("Related-overlap detection is active and caught at least one adjacent expert relationship.")
    else:
        notes.append("No related overlaps were detected; add more overlapping fixtures before trusting duplicate logic.")

    if aggregate["cases_with_probe_need"]:
        notes.append("Some cells still require probes; this is expected for supporting or lower-confidence cells.")
    if aggregate["recommendation_totals"].get("overlap_heavy_needs_stronger_review", 0) > 0:
        notes.append("Some otherwise-positive cases are overlap-heavy and require a stronger admission review.")
    return notes


def render_markdown(calibration: dict[str, Any]) -> str:
    aggregate = calibration["aggregate"]
    lines = [
        "# Candidate Evaluator Leave-One-Out Calibration",
        "",
        f"Generated: {calibration['created_at']}",
        "",
        "## Summary",
        "",
        f"- Cases: {aggregate['case_count']}",
        f"- Total candidate cells: {aggregate['total_candidate_cells']}",
        f"- Total positive impact signals: {aggregate['total_positive_impact']}",
        f"- Total exact overlaps: {aggregate['total_exact_overlaps']}",
        f"- Total related overlaps: {aggregate['total_related_overlaps']}",
        "- Recommendations: "
        + ", ".join(
            f"`{key}`={value}"
            for key, value in aggregate["recommendation_totals"].items()
        ),
        "",
        "## Interpretation",
        "",
    ]
    for note in calibration["calibration_interpretation"]:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Candidate | Baseline | Recommendation | +Impact | Gap | Adjacent | Deepens | Duplicate | Probe | Exact | Related |",
            "|-----------|----------|----------------|---------|-----|----------|---------|-----------|-------|-------|---------|",
        ]
    )
    for case in calibration["cases"]:
        counts = case["classification_counts"]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{case['candidate_expert_id']}`",
                    ", ".join(f"`{item}`" for item in case["baseline_expert_ids"]),
                    f"`{case['preliminary_recommendation']}`",
                    str(case["positive_impact_count"]),
                    str(counts.get("fills_gap", 0)),
                    str(counts.get("adds_adjacent_viewpoint", 0)),
                    str(counts.get("deepens_existing_cell", 0)),
                    str(counts.get("likely_duplicate", 0)),
                    str(counts.get("needs_probe", 0)),
                    str(case["exact_overlap_count"]),
                    str(case["related_overlap_count"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Cell Details", ""])
    for case in calibration["cases"]:
        lines.extend(
            [
                f"### {case['candidate_display_name']}",
                "",
                "| Cell | Classification | Score | Related rollups | Next action |",
                "|------|----------------|-------|-----------------|-------------|",
            ]
        )
        for impact in case["cell_impacts"]:
            related = "<br>".join(f"`{item}`" for item in impact["related_rollups"])
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{impact['candidate_cell_id']}`",
                        impact["classification"],
                        str(impact["aggregate_score"]),
                        related,
                        impact["suggested_next_action"],
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(["## Detailed Report Paths", ""])
    for case in calibration["cases"]:
        report_paths = case.get("report_paths") or {}
        if not report_paths:
            continue
        lines.append(
            f"- `{case['candidate_expert_id']}`: `{report_paths.get('markdown')}`"
        )

    return "\n".join(lines).rstrip() + "\n"


def write_calibration_artifacts(calibration: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    detailed_reports = calibration.pop("_detailed_reports")

    for case in calibration["cases"]:
        expert_id = case["candidate_expert_id"]
        report = detailed_reports[expert_id]
        case_dir = out_dir / "per_candidate" / expert_id
        json_path = case_dir / "candidate_impact_report.json"
        md_path = case_dir / "candidate_impact_report.md"
        write_json(json_path, report)
        md_path.write_text(candidate_eval.render_markdown(report), encoding="utf-8")
        case["report_paths"] = {
            "json": str(json_path),
            "markdown": str(md_path),
        }

    json_path = out_dir / "leave_one_out_summary.json"
    md_path = out_dir / "leave_one_out_summary.md"
    write_json(json_path, calibration)
    md_path.write_text(render_markdown(calibration), encoding="utf-8")
    return {
        "json": json_path,
        "markdown": md_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate candidate evaluator with leave-one-out runs.")
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
        help="Ignore the admission manifest and calibrate on every normalized passport under input root.",
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
    passport_paths = matrix_builder.select_passports(
        input_root=args.input_root,
        explicit_passports=args.passports,
        admission_manifest_path=args.admission_manifest,
        include_all_passports=args.include_all_passports,
    )
    if len(passport_paths) < 2:
        raise SystemExit(f"Need at least 2 normalized passports for calibration under {args.input_root}")

    calibration = build_calibration(passport_paths)
    paths = write_calibration_artifacts(calibration, args.out_dir)
    print(f"Wrote {paths['json']}")
    print(f"Wrote {paths['markdown']}")
    print(json.dumps(calibration["aggregate"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
