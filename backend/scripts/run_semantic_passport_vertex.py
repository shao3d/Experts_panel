#!/usr/bin/env python3
"""Run a prepared semantic passport packet through Vertex AI.

This script performs the paid/live step for a packet produced by
export_semantic_passport_packet.py. It first calls countTokens, then optionally
calls generateContent, and saves raw responses plus a compact receipt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_PACKET_DIR = (
    REPO_ROOT / "output" / "expert_admission" / "semantic_passports" / "refat" / "input"
)
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_MAX_OUTPUT_TOKENS = 65536
DEFAULT_TEMPERATURE = 0.1
SOURCE_REF_RE = re.compile(r"^P\d{4}(?:\.C\d{4})?$")
MATRIX_EXPORT_REPAIR_WEIGHTS = {"strong", "signature"}

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_local_env() -> None:
    """Load local env files without overriding explicit shell env."""

    for env_path in (BACKEND_DIR / ".env", REPO_ROOT / ".env"):
        if env_path.exists():
            load_dotenv(env_path, override=False)


def resolve_location(model: str, configured_location: str) -> str:
    if model.startswith("gemini-3"):
        return "global"
    return configured_location


def build_url(project_id: str, location: str, model: str, method: str) -> str:
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return (
        f"https://{host}/v1/"
        f"projects/{project_id}/locations/{location}/publishers/google/models/{model}:{method}"
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_text(vertex_response: dict[str, Any]) -> str:
    candidates = vertex_response.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


def post_vertex(url: str, token: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"raw_text": response.text}

    if response.ok:
        return body

    raise RuntimeError(
        "Vertex request failed "
        f"status={response.status_code} body={json.dumps(body, ensure_ascii=False)[:2000]}"
    )


def parse_generated_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def collect_source_refs(value: Any) -> set[str]:
    refs: set[str] = set()

    def visit(inner: Any) -> None:
        if isinstance(inner, dict):
            for child in inner.values():
                visit(child)
        elif isinstance(inner, list):
            for child in inner:
                visit(child)
        elif isinstance(inner, str) and SOURCE_REF_RE.match(inner):
            refs.add(inner)

    visit(value)
    return refs


def first_query_intent_id(cell: dict[str, Any]) -> str | None:
    query_intent_ids = cell.get("query_intent_ids") or []
    if not query_intent_ids:
        return None
    return str(query_intent_ids[0])


def matrix_cell_key(cell: dict[str, Any]) -> str | None:
    domain_id = cell.get("domain_id")
    subdomain_id = cell.get("subdomain_id")
    query_intent_id = first_query_intent_id(cell)
    if not domain_id or not subdomain_id or not query_intent_id:
        return None
    return f"{domain_id}/{subdomain_id}/{query_intent_id}"


def matrix_cell_weight(cell: dict[str, Any]) -> str:
    return str(cell.get("recommended_matrix_weight") or "").strip().lower()


def is_matrix_export_repair_candidate(cell: dict[str, Any]) -> bool:
    return matrix_cell_weight(cell) in MATRIX_EXPORT_REPAIR_WEIGHTS


def number_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def coverage_level_from_weight(weight: str) -> str:
    if weight in {"signature", "strong"}:
        return "strong"
    if weight == "normal":
        return "moderate"
    if weight == "weak":
        return "thin"
    return "none"


def source_role_from_weight(weight: str) -> str:
    if weight in {"signature", "strong"}:
        return "primary"
    if weight == "normal":
        return "supporting"
    if weight == "weak":
        return "weak"
    return "avoid"


def depth_level_from_score(score: float) -> str:
    if score >= 4.5:
        return "deep_practitioner"
    if score >= 2.5:
        return "practical"
    if score > 0:
        return "commentary"
    return "none"


def missing_matrix_export_cells(passport: dict[str, Any]) -> list[dict[str, Any]]:
    matrix_export_cells = (passport.get("matrix_export") or {}).get("cells") or []
    exported_keys = {
        key
        for key in (matrix_cell_key(cell) for cell in matrix_export_cells)
        if key is not None
    }
    missing: list[dict[str, Any]] = []
    for cell in passport.get("matrix_cells") or []:
        if not is_matrix_export_repair_candidate(cell):
            continue
        key = matrix_cell_key(cell)
        if key is None or key in exported_keys:
            continue
        missing.append(
            {
                "cell_id": key,
                "domain_id": cell.get("domain_id"),
                "subdomain_id": cell.get("subdomain_id"),
                "query_intent_ids": cell.get("query_intent_ids") or [],
                "recommended_matrix_weight": cell.get("recommended_matrix_weight"),
                "evidence_refs": cell.get("evidence_refs") or [],
            }
        )
    return missing


def export_cell_from_matrix_cell(cell: dict[str, Any]) -> dict[str, Any] | None:
    cell_id = matrix_cell_key(cell)
    evidence_refs = cell.get("evidence_refs") or []
    if cell_id is None or not evidence_refs:
        return None

    weight = matrix_cell_weight(cell)
    depth_score = number_score(cell.get("depth_score_0_5"))
    derived: dict[str, Any] = {
        "cell_id": cell_id,
        "domain_id": cell["domain_id"],
        "subdomain_id": cell["subdomain_id"],
        "subdomain_name": cell.get("subdomain_name"),
        "query_intent_ids": cell.get("query_intent_ids") or [],
        "coverage_level": coverage_level_from_weight(weight),
        "depth_level": depth_level_from_score(depth_score),
        "source_role": source_role_from_weight(weight),
        "scores": {
            "depth": depth_score,
            "practicality": number_score(cell.get("practicality_score_0_5")),
            "evidence_quality": number_score(cell.get("evidence_quality_score_0_5")),
            "source_utility": number_score(cell.get("source_utility_score_0_5")),
            "intrinsic_distinctiveness": number_score(
                cell.get("intrinsic_distinctiveness_score_0_5")
            ),
            "anti_hype": number_score(cell.get("anti_hype_score_0_5")),
            "community_signal": number_score(cell.get("comment_signal_score_0_5")),
        },
        "matrix_update_role": "needs_matrix_compare",
        "limitations": [
            "Deterministically repaired from matrix_cells because matrix_export omitted this matrix-worthy cell."
        ],
        "evidence_refs": evidence_refs,
        "derived_from": "matrix_cells",
        "repair_reason": "matrix_export_omitted_strong_or_signature_cell",
    }
    if "confidence" in cell:
        derived["confidence"] = cell["confidence"]
    return derived


def repair_matrix_export_from_matrix_cells(passport: dict[str, Any]) -> dict[str, Any]:
    matrix_export = passport.setdefault("matrix_export", {})
    export_cells = matrix_export.setdefault("cells", [])
    exported_keys = {
        key
        for key in (matrix_cell_key(cell) for cell in export_cells)
        if key is not None
    }

    repaired_cells: list[dict[str, Any]] = []
    skipped_cells: list[str] = []
    for cell in passport.get("matrix_cells") or []:
        if not is_matrix_export_repair_candidate(cell):
            continue
        key = matrix_cell_key(cell)
        if key is None:
            skipped_cells.append("missing_required_identity")
            continue
        if key in exported_keys:
            continue
        export_cell = export_cell_from_matrix_cell(cell)
        if export_cell is None:
            skipped_cells.append(key)
            continue
        export_cells.append(export_cell)
        exported_keys.add(key)
        repaired_cells.append(export_cell)

    passport.setdefault("audit", {}).setdefault("normalization_notes", []).append(
        {
            "operation": "repair_matrix_export_from_matrix_cells",
            "repaired_cell_count": len(repaired_cells),
            "repaired_cell_ids": [cell["cell_id"] for cell in repaired_cells],
            "skipped_cell_count": len(skipped_cells),
            "skipped_cells": skipped_cells,
        }
    )
    return passport


def normalize_passport(
    passport: dict[str, Any],
    source_ref_index: list[dict[str, Any]],
    expected_generated_at: str,
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(passport, ensure_ascii=False))
    normalized.setdefault("passport_meta", {})["generated_at"] = expected_generated_at

    source_ref_lookup = {entry["source_ref"]: entry for entry in source_ref_index}
    used_refs = collect_source_refs(normalized)
    indexed_refs = {
        entry.get("source_ref")
        for entry in normalized.get("source_ref_index_used") or []
        if isinstance(entry, dict) and entry.get("source_ref")
    }

    hydrated_entries = []
    for ref in sorted(used_refs - indexed_refs):
        source_entry = source_ref_lookup.get(ref)
        if not source_entry:
            continue
        hydrated = {
            "source_ref": source_entry["source_ref"],
            "source_kind": source_entry["source_kind"],
            "post_id": source_entry["post_id"],
            "telegram_message_id": source_entry["telegram_message_id"],
            "comment_id": source_entry["comment_id"],
            "telegram_comment_id": source_entry["telegram_comment_id"],
            "created_at": source_entry["created_at"],
            "why_used": "Cited elsewhere in passport; hydrated by deterministic post-processor.",
        }
        hydrated_entries.append(hydrated)

    normalized.setdefault("source_ref_index_used", []).extend(hydrated_entries)
    normalized = repair_matrix_export_from_matrix_cells(normalized)
    normalized.setdefault("audit", {}).setdefault("normalization_notes", []).append(
        {
            "operation": "hydrate_source_ref_index_used",
            "hydrated_ref_count": len(hydrated_entries),
            "generated_at_set_from_manifest": expected_generated_at,
        }
    )
    return normalized


def validate_passport(
    passport: dict[str, Any],
    source_ref_index: list[dict[str, Any]],
    expected_generated_at: str | None = None,
) -> dict[str, Any]:
    required = [
        "passport_meta",
        "corpus_audit",
        "source_ref_index_used",
        "executive_summary",
        "expert_positioning",
        "knowledge_domains",
        "value_dimensions",
        "matrix_cells",
        "query_intent_fit",
        "content_quality_distribution",
        "matrix_export",
        "signature_insights",
        "practical_patterns",
        "claims_and_positions",
        "source_utility",
        "community_signal",
        "admission_implications",
        "audit",
    ]
    missing = [key for key in required if key not in passport]
    known_refs = {entry["source_ref"] for entry in source_ref_index}
    used_refs = collect_source_refs(passport)

    unknown_refs = sorted(ref for ref in used_refs if ref not in known_refs)
    indexed_used_refs = {
        entry.get("source_ref")
        for entry in passport.get("source_ref_index_used") or []
        if isinstance(entry, dict) and entry.get("source_ref")
    }
    refs_missing_from_source_ref_index_used = sorted(used_refs - indexed_used_refs)
    matrix_export = passport.get("matrix_export") or {}
    matrix_export_cells = matrix_export.get("cells") or []
    matrix_cells = passport.get("matrix_cells") or []
    missing_export_cells = missing_matrix_export_cells(passport)
    passport_generated_at = (passport.get("passport_meta") or {}).get("generated_at")
    generated_at_matches_expected = (
        expected_generated_at is None or passport_generated_at == expected_generated_at
    )
    bad_relative_novelty = []
    for cell in passport.get("matrix_cells") or []:
        novelty = cell.get("matrix_relative_novelty")
        if novelty is not None and novelty != "not_scored_without_matrix":
            bad_relative_novelty.append(novelty)

    return {
        "missing_required_top_level_keys": missing,
        "known_source_ref_count": len(known_refs),
        "used_source_ref_count": len(used_refs),
        "source_ref_index_used_count": len(indexed_used_refs),
        "unknown_source_refs": unknown_refs[:50],
        "unknown_source_ref_count": len(unknown_refs),
        "refs_missing_from_source_ref_index_used": refs_missing_from_source_ref_index_used[:50],
        "refs_missing_from_source_ref_index_used_count": len(
            refs_missing_from_source_ref_index_used
        ),
        "matrix_cell_count": len(matrix_cells),
        "matrix_export_cell_count": len(matrix_export_cells),
        "matrix_export_incomplete": bool(missing_export_cells),
        "missing_matrix_export_cells": missing_export_cells[:50],
        "missing_matrix_export_cell_count": len(missing_export_cells),
        "bad_matrix_relative_novelty_values": bad_relative_novelty,
        "passport_generated_at": passport_generated_at,
        "expected_generated_at": expected_generated_at,
        "generated_at_matches_expected": generated_at_matches_expected,
        "valid_basic_contract": (
            not missing
            and not unknown_refs
            and not refs_missing_from_source_ref_index_used
            and len(matrix_export_cells) > 0
            and not missing_export_cells
            and not bad_relative_novelty
            and generated_at_matches_expected
        ),
    }


async def run(args: argparse.Namespace) -> int:
    load_local_env()
    from backend.src.services.vertex_ai_auth import (  # noqa: WPS433
        VertexAICredentialsError,
        get_vertex_ai_auth_manager,
    )

    packet_dir = args.packet_dir.resolve()
    manifest = read_json(packet_dir / "run_manifest.json")
    expert_id = manifest["corpus_stats"]["expert_id"]
    model = args.model or manifest["model"]
    prompt_path = packet_dir / manifest["files"]["combined_prompt"]
    source_ref_index_path = packet_dir / manifest["files"]["source_ref_index"]
    output_dir = (args.output_dir or packet_dir.parent / "output").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = prompt_path.read_text(encoding="utf-8")
    source_ref_index = json.loads(source_ref_index_path.read_text(encoding="utf-8"))

    if args.validate_existing:
        passport_name = (
            f"{expert_id}_semantic_passport.normalized.json"
            if args.normalized
            else f"{expert_id}_semantic_passport.json"
        )
        passport_path = output_dir / passport_name
        passport = read_json(passport_path)
        validation = validate_passport(
            passport,
            source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        write_json(output_dir / f"{expert_id}_semantic_passport_validation.json", validation)
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0 if validation["valid_basic_contract"] else 2

    if args.normalize_existing:
        passport_path = output_dir / f"{expert_id}_semantic_passport.json"
        passport = read_json(passport_path)
        normalized = normalize_passport(
            passport,
            source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        normalized_path = output_dir / f"{expert_id}_semantic_passport.normalized.json"
        write_json(normalized_path, normalized)
        validation = validate_passport(
            normalized,
            source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        write_json(output_dir / f"{expert_id}_semantic_passport.normalized_validation.json", validation)
        print(json.dumps({"normalized_path": str(normalized_path), "validation": validation}, ensure_ascii=False, indent=2))
        return 0 if validation["valid_basic_contract"] else 2

    auth_manager = get_vertex_ai_auth_manager()
    if not auth_manager.is_configured():
        raise VertexAICredentialsError("Vertex AI credentials are not configured")

    location = resolve_location(model, auth_manager.location)
    token = await auth_manager.get_access_token()
    contents = [{"role": "user", "parts": [{"text": prompt}]}]

    count_payload = {"contents": contents}
    count_url = build_url(auth_manager.project_id, location, model, "countTokens")
    count_started_at = datetime.now(timezone.utc).isoformat()
    count_response = post_vertex(count_url, token, count_payload, args.timeout_seconds)
    count_finished_at = datetime.now(timezone.utc).isoformat()
    write_json(output_dir / f"{expert_id}_count_tokens_response.json", count_response)

    receipt: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "packet_dir": str(packet_dir),
        "prompt_path": str(prompt_path),
        "model": model,
        "project_id": auth_manager.project_id,
        "location": location,
        "count_tokens": {
            "started_at": count_started_at,
            "finished_at": count_finished_at,
            "response": count_response,
        },
        "generate": None,
    }

    if args.count_only:
        receipt["status"] = "count_only"
        write_json(output_dir / f"{expert_id}_semantic_passport_receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0

    generation_config = {
        "temperature": args.temperature,
        "candidateCount": 1,
        "maxOutputTokens": args.max_output_tokens,
        "responseMimeType": "application/json",
    }
    generate_payload = {
        "contents": contents,
        "generationConfig": generation_config,
    }
    generate_url = build_url(auth_manager.project_id, location, model, "generateContent")
    generate_started_at = datetime.now(timezone.utc).isoformat()
    generate_response = post_vertex(generate_url, token, generate_payload, args.timeout_seconds)
    generate_finished_at = datetime.now(timezone.utc).isoformat()
    write_json(output_dir / f"{expert_id}_generate_content_response.json", generate_response)

    generated_text = extract_text(generate_response)
    (output_dir / f"{expert_id}_semantic_passport.raw.txt").write_text(
        generated_text,
        encoding="utf-8",
    )
    parsed_passport, parse_error = parse_generated_json(generated_text)
    validation = None
    if parsed_passport is not None:
        write_json(output_dir / f"{expert_id}_semantic_passport.json", parsed_passport)
        validation = validate_passport(
            parsed_passport,
            source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        write_json(output_dir / f"{expert_id}_semantic_passport_validation.json", validation)

    receipt["generate"] = {
        "started_at": generate_started_at,
        "finished_at": generate_finished_at,
        "generation_config": generation_config,
        "usage_metadata": generate_response.get("usageMetadata", {}),
        "model_version": generate_response.get("modelVersion"),
        "finish_reason": (
            (generate_response.get("candidates") or [{}])[0].get("finishReason")
            if generate_response.get("candidates")
            else None
        ),
        "text_chars": len(generated_text),
        "json_parse_error": parse_error,
        "validation": validation,
    }
    receipt["status"] = "generated" if parsed_passport is not None else "generated_unparsed"
    write_json(output_dir / f"{expert_id}_semantic_passport_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if parsed_passport is not None else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a semantic passport packet through Vertex AI.")
    parser.add_argument("--packet-dir", type=Path, default=DEFAULT_PACKET_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--count-only", action="store_true")
    parser.add_argument("--validate-existing", action="store_true")
    parser.add_argument("--normalize-existing", action="store_true")
    parser.add_argument("--normalized", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
