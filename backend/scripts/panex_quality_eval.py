#!/usr/bin/env python3
"""Evaluate final Panex answers against product-quality scenarios."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import load_backend_env


PRODUCTION_API_URL = "https://experts-panel.fly.dev/api/v1/agent/context"
DEFAULT_TIMEOUT_SECONDS = 3600.0
DEFAULT_SCENARIOS_PATH = (
    BACKEND_DIR / "tests" / "fixtures" / "panex_quality_scenarios.json"
)
DEFAULT_REPORT_PATH = BACKEND_DIR / "test_results" / "panex_quality_eval" / "latest.json"
SOURCE_HANDLE_RE = re.compile(r"\b([a-z][a-z0-9_]+):(\d+)\b", re.IGNORECASE)
RAW_JSON_MARKERS = ['"mode": "expert_digest"', '"experts": [', '"source_refs": [']


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Панэкс final answers against product-quality rubric.",
    )
    parser.add_argument(
        "--scenarios-path",
        default=str(DEFAULT_SCENARIOS_PATH),
        help=f"Scenario JSON path. Default: {DEFAULT_SCENARIOS_PATH}.",
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        help="Scenario id to evaluate. Repeatable. Defaults to all scenarios.",
    )
    parser.add_argument(
        "--answer-file",
        help="Markdown/text answer file for a single selected scenario.",
    )
    parser.add_argument(
        "--answers-dir",
        help="Directory with one '<scenario_id>.md' answer file per scenario.",
    )
    parser.add_argument(
        "--digest-dir",
        help="Optional directory with one '<scenario_id>.json' digest/source_expand payload per scenario.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch fresh production digest/source context for each scenario.",
    )
    parser.add_argument(
        "--api-url",
        default=PRODUCTION_API_URL,
        help=f"Agent Context API URL for --live. Default: {PRODUCTION_API_URL}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Live request timeout in seconds. Default: 3600.",
    )
    parser.add_argument(
        "--write-digests-dir",
        help="When --live is set, also write fetched payloads as '<scenario_id>.json'.",
    )
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help=f"Where to write JSON report. Default: {DEFAULT_REPORT_PATH}.",
    )
    parser.add_argument(
        "--print-scenarios",
        action="store_true",
        help="Print scenario ids/titles and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scenarios = load_scenarios(Path(args.scenarios_path))
    selected_scenarios = select_scenarios(scenarios, args.scenario_id)

    if args.print_scenarios:
        for scenario in selected_scenarios:
            print(f"{scenario['id']}\t{scenario['title']}")
        return 0

    if args.answer_file and len(selected_scenarios) != 1:
        print("--answer-file requires exactly one --scenario-id", file=sys.stderr)
        return 2

    load_backend_env(BACKEND_DIR / ".env")
    token = os.getenv("AGENT_CONTEXT_API_TOKEN", "").strip()
    if args.live and not token:
        print("AGENT_CONTEXT_API_TOKEN is required when --live is set", file=sys.stderr)
        return 2

    report = build_report(
        selected_scenarios,
        answer_file=Path(args.answer_file) if args.answer_file else None,
        answers_dir=Path(args.answers_dir) if args.answers_dir else None,
        digest_dir=Path(args.digest_dir) if args.digest_dir else None,
        live=bool(args.live),
        api_url=args.api_url,
        timeout_seconds=args.timeout,
        token=token,
        write_digests_dir=Path(args.write_digests_dir) if args.write_digests_dir else None,
    )
    write_report(Path(args.report_path), report)
    print_status(report)
    return 0 if report["status"] == "passed" else 1


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("Panex quality scenarios version must be 1")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Panex quality scenarios file must contain scenarios")
    return scenarios


def select_scenarios(
    scenarios: list[dict[str, Any]],
    scenario_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if not scenario_ids:
        return scenarios
    by_id = {scenario["id"]: scenario for scenario in scenarios}
    missing = [scenario_id for scenario_id in scenario_ids if scenario_id not in by_id]
    if missing:
        raise ValueError(f"Unknown scenario ids: {', '.join(missing)}")
    return [by_id[scenario_id] for scenario_id in scenario_ids]


def build_report(
    scenarios: list[dict[str, Any]],
    *,
    answer_file: Path | None,
    answers_dir: Path | None,
    digest_dir: Path | None,
    live: bool,
    api_url: str,
    timeout_seconds: float,
    token: str,
    write_digests_dir: Path | None,
) -> dict[str, Any]:
    results = []
    for scenario in scenarios:
        answer_text = load_answer_text(
            scenario_id=scenario["id"],
            answer_file=answer_file,
            answers_dir=answers_dir,
        )
        digest_payload = load_digest_payload(
            scenario=scenario,
            digest_dir=digest_dir,
            live=live,
            api_url=api_url,
            timeout_seconds=timeout_seconds,
            token=token,
            write_digests_dir=write_digests_dir,
        )
        results.append(
            evaluate_scenario(
                scenario=scenario,
                answer_text=answer_text,
                digest_payload=digest_payload,
            )
        )

    status = aggregate_status(results)
    return {
        "status": status,
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["status"] == "passed"),
            "failed": sum(1 for result in results if result["status"] == "failed"),
            "needs_answer": sum(
                1 for result in results if result["status"] == "needs_answer"
            ),
        },
        "scenarios": results,
    }


def load_answer_text(
    *,
    scenario_id: str,
    answer_file: Path | None,
    answers_dir: Path | None,
) -> str | None:
    if answer_file:
        return answer_file.read_text(encoding="utf-8")
    if answers_dir:
        path = answers_dir / f"{scenario_id}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def load_digest_payload(
    *,
    scenario: dict[str, Any],
    digest_dir: Path | None,
    live: bool,
    api_url: str,
    timeout_seconds: float,
    token: str,
    write_digests_dir: Path | None,
) -> dict[str, Any] | None:
    scenario_id = scenario["id"]
    if live:
        if scenario.get("response_mode") != "expert_digest":
            return None
        payload = call_agent_context_api(
            token=token,
            api_url=api_url,
            request_payload=build_agent_context_payload(scenario),
            timeout_seconds=timeout_seconds,
        )
        if write_digests_dir:
            write_digests_dir.mkdir(parents=True, exist_ok=True)
            (write_digests_dir / f"{scenario_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return payload
    if digest_dir:
        path = digest_dir / f"{scenario_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def build_agent_context_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    selection = scenario.get("selection") or {}
    return {
        "query": scenario["query"],
        "response_mode": "expert_digest",
        "expert_scope": selection.get("expert_scope", "custom"),
        "expert_group": selection.get("expert_group"),
        "expert_filter": selection.get("expert_filter"),
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": bool(selection.get("use_recent_only", False)),
        "use_super_passport": True,
    }


def call_agent_context_api(
    *,
    token: str,
    api_url: str,
    request_payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    response = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {token}"},
        json=request_payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def evaluate_scenario(
    *,
    scenario: dict[str, Any],
    answer_text: str | None,
    digest_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if not answer_text or not answer_text.strip():
        return {
            "id": scenario["id"],
            "title": scenario["title"],
            "status": "needs_answer",
            "score": None,
            "min_score": scenario["rubric"]["min_score"],
            "checks": [],
            "critical_issues": ["missing_panex_answer"],
            "digest_context": summarize_digest_context(digest_payload),
        }

    checks = build_checks(scenario, answer_text, digest_payload)
    total_weight = sum(check["weight"] for check in checks)
    weighted_score = sum(check["score"] * check["weight"] for check in checks)
    score = round(weighted_score / total_weight, 3) if total_weight else 0.0
    critical_issues = [
        check["id"] for check in checks if check.get("critical") and check["score"] < 1
    ]
    min_score = float(scenario["rubric"]["min_score"])
    status = "passed" if score >= min_score and not critical_issues else "failed"
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "status": status,
        "score": score,
        "min_score": min_score,
        "checks": checks,
        "critical_issues": critical_issues,
        "digest_context": summarize_digest_context(digest_payload),
    }


def build_checks(
    scenario: dict[str, Any],
    answer_text: str,
    digest_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rubric = scenario["rubric"]
    normalized = normalize(answer_text)
    return [
        check_raw_json(answer_text),
        check_request_passport(scenario, normalized),
        check_scope_fidelity(scenario, normalized),
        check_source_grounding(scenario, answer_text, digest_payload),
        check_signal_honesty(normalized),
        check_required_coverage(rubric, normalized),
        check_actionability(rubric, normalized),
        check_brevity(rubric, answer_text),
        check_expand_path(rubric, normalized),
        check_external_boundary(normalized),
    ]


def check_raw_json(answer_text: str) -> dict[str, Any]:
    stripped = answer_text.strip()
    looks_like_raw_json = stripped.startswith("{") or all(
        marker in answer_text for marker in RAW_JSON_MARKERS[:2]
    )
    return make_check(
        "not_raw_json",
        weight=1.5,
        score=0.0 if looks_like_raw_json else 1.0,
        details="Final answer must be synthesized prose, not raw API JSON.",
        critical=True,
    )


def check_request_passport(scenario: dict[str, Any], normalized: str) -> dict[str, Any]:
    response_mode = scenario.get("response_mode")
    if response_mode == "source_expand":
        terms = [
            "source_keys_sent",
            "target",
            "mode",
            "warnings",
            "source_expand",
            "request passport",
        ]
        required_hits = 4
        details_label = "source_expand Request passport markers"
    else:
        terms = [
            "query_sent",
            "experts_sent",
            "response_mode",
            "target",
            "warnings",
            "query and selection",
        ]
        required_hits = 4
        details_label = "expert_digest Request passport markers"

    hits = count_hits(normalized, terms)
    return make_check(
        "request_passport",
        weight=1.0,
        score=min(1.0, hits / required_hits),
        details=f"Matched {hits}/{len(terms)} {details_label}.",
    )


def check_scope_fidelity(scenario: dict[str, Any], normalized: str) -> dict[str, Any]:
    selection = scenario.get("selection") or {}
    expected_terms = []
    if selection.get("expert_group"):
        group = selection["expert_group"]
        expected_terms.extend([group, group.replace("_", " "), "tech & business"])
    expected_terms.extend(selection.get("expert_filter") or [])
    hits = count_hits(normalized, expected_terms)
    needed = 1 if selection.get("expert_group") else max(1, len(expected_terms))
    return make_check(
        "scope_fidelity",
        weight=1.0,
        score=min(1.0, hits / needed),
        details=f"Matched {hits}/{len(expected_terms)} expected scope terms.",
    )


def check_source_grounding(
    scenario: dict[str, Any],
    answer_text: str,
    digest_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    handles = set(SOURCE_HANDLE_RE.findall(answer_text))
    answer_source_keys = {f"{expert}:{message_id}" for expert, message_id in handles}
    expected_source_keys = source_keys_from_digest(digest_payload)
    min_handles = int(scenario["rubric"].get("min_source_handles", 1))

    if expected_source_keys:
        matched = answer_source_keys & expected_source_keys
        score = min(1.0, len(matched) / min_handles)
        details = (
            f"Matched {len(matched)} digest source handles; "
            f"answer handles={len(answer_source_keys)}."
        )
    else:
        expected_experts = set((scenario.get("selection") or {}).get("expert_filter") or [])
        matched = {
            source_key
            for source_key in answer_source_keys
            if source_key.split(":", 1)[0] in expected_experts
        }
        score = min(1.0, len(matched or answer_source_keys) / min_handles)
        details = (
            "No digest payload supplied; checked source-handle shape and expert ids. "
            f"answer handles={len(answer_source_keys)}."
        )

    return make_check(
        "source_grounding",
        weight=1.5,
        score=score,
        details=details,
    )


def check_signal_honesty(normalized: str) -> dict[str, Any]:
    forbidden = [
        "scientifically proven",
        "proven fact",
        "железно доказано",
        "строго доказано",
        "это факт",
    ]
    caution_terms = [
        "сигнал",
        "по источникам",
        "по этим источникам",
        "мнение",
        "похоже",
        "огранич",
        "слаб",
        "не видно",
        "недостаточно",
        "caveat",
    ]
    has_forbidden = any(term in normalized for term in forbidden)
    caution_hits = count_hits(normalized, caution_terms)
    score = 0.0 if has_forbidden else min(1.0, caution_hits / 2)
    return make_check(
        "signal_honesty",
        weight=1.25,
        score=score,
        details=f"Forbidden proof framing={has_forbidden}; caution hits={caution_hits}.",
        critical=has_forbidden,
    )


def check_required_coverage(rubric: dict[str, Any], normalized: str) -> dict[str, Any]:
    groups = rubric.get("must_cover_any") or []
    if not groups:
        return make_check("coverage", weight=1.25, score=1.0, details="No must-cover groups.")
    covered = sum(1 for terms in groups if any(term in normalized for term in terms))
    return make_check(
        "coverage",
        weight=1.5,
        score=covered / len(groups),
        details=f"Covered {covered}/{len(groups)} must-cover groups.",
    )


def check_actionability(rubric: dict[str, Any], normalized: str) -> dict[str, Any]:
    terms = rubric.get("action_terms") or ["когда", "если", "следующий", "критер"]
    hits = count_hits(normalized, terms)
    return make_check(
        "actionability",
        weight=1.0,
        score=min(1.0, hits / 3),
        details=f"Matched {hits}/{len(terms)} action terms.",
    )


def check_brevity(rubric: dict[str, Any], answer_text: str) -> dict[str, Any]:
    max_chars = int(rubric.get("max_answer_chars", 7000))
    min_chars = int(rubric.get("min_answer_chars", 700))
    answer_len = len(answer_text)
    if answer_len > max_chars:
        score = max(0.0, max_chars / answer_len)
    elif answer_len < min_chars:
        score = max(0.0, answer_len / min_chars)
    else:
        score = 1.0
    return make_check(
        "brevity",
        weight=0.75,
        score=score,
        details=f"Answer length {answer_len}; expected {min_chars}-{max_chars} chars.",
    )


def check_expand_path(rubric: dict[str, Any], normalized: str) -> dict[str, Any]:
    if not rubric.get("expect_expansion_offer", True):
        return make_check(
            "expand_path",
            weight=0.75,
            score=1.0,
            details="Scenario does not require an expansion offer.",
        )
    terms = [
        "source_expand",
        "source_key",
        "раскры",
        "показать источник",
        "раскрыть источник",
        "комментар",
        "углуб",
    ]
    hits = count_hits(normalized, terms)
    return make_check(
        "expand_path",
        weight=0.75,
        score=min(1.0, hits / 1),
        details=f"Matched {hits} source expansion terms.",
    )


def check_external_boundary(normalized: str) -> dict[str, Any]:
    forbidden = [
        "я открыл ссыл",
        "я перешел по ссыл",
        "я сходил по ссыл",
        "я склонировал",
        "я скачал github",
        "fetched external",
        "crawled external",
    ]
    has_forbidden = any(term in normalized for term in forbidden)
    return make_check(
        "external_boundary",
        weight=0.75,
        score=0.0 if has_forbidden else 1.0,
        details=f"Forbidden external-fetch claims={has_forbidden}.",
        critical=has_forbidden,
    )


def make_check(
    check_id: str,
    *,
    weight: float,
    score: float,
    details: str,
    critical: bool = False,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "passed" if score >= 1.0 else "failed",
        "score": round(max(0.0, min(1.0, score)), 3),
        "weight": weight,
        "details": details,
        "critical": critical,
    }


def summarize_digest_context(digest_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not digest_payload:
        return {"available": False}
    experts = digest_payload.get("experts") or []
    return {
        "available": True,
        "mode": digest_payload.get("mode"),
        "expert_ids": [expert.get("expert_id") for expert in experts],
        "warnings": digest_payload.get("warnings") or [],
        "source_keys_count": len(source_keys_from_digest(digest_payload)),
    }


def source_keys_from_digest(digest_payload: dict[str, Any] | None) -> set[str]:
    if not digest_payload:
        return set()
    source_keys = set()
    for expert in digest_payload.get("experts") or []:
        digest = expert.get("digest") or {}
        for source_ref in digest.get("source_refs") or []:
            source_key = source_ref.get("source_key")
            if source_key:
                source_keys.add(source_key)
        for source_index in digest.get("source_index") or []:
            source_key = source_index.get("source_key")
            if source_key:
                source_keys.add(source_key)
    for source in digest_payload.get("sources") or []:
        source_key = source.get("source_key")
        if source_key:
            source_keys.add(source_key)
    return source_keys


def aggregate_status(results: list[dict[str, Any]]) -> str:
    if any(result["status"] == "failed" for result in results):
        return "failed"
    if any(result["status"] == "needs_answer" for result in results):
        return "needs_answer"
    return "passed"


def count_hits(normalized: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term and normalize(term) in normalized)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def print_status(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        "panex_quality_eval: "
        f"{report['status']} "
        f"({summary['passed']} passed, {summary['failed']} failed, "
        f"{summary['needs_answer']} needs_answer)"
    )
    for result in report["scenarios"]:
        score = "n/a" if result["score"] is None else f"{result['score']:.3f}"
        print(f"- {result['id']}: {result['status']} score={score}")


if __name__ == "__main__":
    raise SystemExit(main())
