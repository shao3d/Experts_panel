#!/usr/bin/env python3
"""Live local smoke helper for the explicit Agent Context API."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import load_backend_env


DEFAULT_QUERY = "AI agents for sales"
DEFAULT_EXPERTS = "refat,akimov"
DEFAULT_TIMEOUT_SECONDS = 3600.0
CLI_TIMEOUT_GRACE_SECONDS = 30.0
DEFAULT_REPORT_PATH = (
    BACKEND_DIR / "test_results" / "agent_context_live_smoke" / "latest.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a live local smoke test for the Agent Context API.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"Query to send through the Agent Context CLI. Default: {DEFAULT_QUERY!r}.",
    )
    parser.add_argument(
        "--experts",
        default=DEFAULT_EXPERTS,
        help=f"Comma-separated expert IDs. Default: {DEFAULT_EXPERTS}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Overall readiness/CLI timeout in seconds. Default: 3600.",
    )
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help=f"Where to write sanitized smoke report. Default: {DEFAULT_REPORT_PATH}.",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Treat missing local readiness as a nonzero failure instead of skipped.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_backend_env(BACKEND_DIR / ".env")

    report_path = Path(args.report_path)
    token = os.getenv("AGENT_CONTEXT_API_TOKEN", "").strip()
    if not token:
        status = "failed" if args.require_live else "skipped"
        report = _base_report(
            status=status,
            reason="missing_agent_context_api_token",
            message=(
                "AGENT_CONTEXT_API_TOKEN is required for live local smoke. "
                "Configure it in backend/.env or the shell environment."
            ),
            query=args.query,
            experts=_parse_experts(args.experts),
        )
        _write_report(report_path, report)
        _print_status(report)
        return 1 if args.require_live else 0

    process = None
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    api_url = f"{base_url}/api/v1/agent/context"
    experts = _parse_experts(args.experts)

    try:
        process = _start_backend(port)
        if not _wait_for_health(base_url, args.timeout):
            report = _base_report(
                status="failed",
                reason="backend_health_unavailable",
                message=(
                    "Local backend did not become healthy before timeout. "
                    "Check backend startup logs and local runtime configuration."
                ),
                query=args.query,
                experts=experts,
                api_url=api_url,
            )
            _write_report(report_path, report)
            _print_status(report)
            return 1

        try:
            cli_result = _run_cli(
                query=args.query,
                experts=args.experts,
                api_url=api_url,
                timeout_seconds=args.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            report = _base_report(
                status="failed",
                reason="cli_timeout",
                message=(
                    "Agent Context CLI subprocess exceeded the smoke timeout. "
                    "Raise the helper timeout or narrow the query/expert selection."
                ),
                query=args.query,
                experts=experts,
                api_url=api_url,
                error=_sanitize_text(str(exc), [token]),
            )
            _write_report(report_path, report)
            _print_status(report)
            return 1
        if cli_result.returncode != 0:
            raw_error = cli_result.stderr or cli_result.stdout
            failure_reason, failure_message = _classify_cli_failure(raw_error)
            report = _base_report(
                status="failed",
                reason=failure_reason,
                message=failure_message,
                query=args.query,
                experts=experts,
                api_url=api_url,
                error=_sanitize_text(raw_error, [token]),
            )
            _write_report(report_path, report)
            _print_status(report)
            return 1

        try:
            payload = json.loads(cli_result.stdout)
        except json.JSONDecodeError:
            report = _base_report(
                status="failed",
                reason="cli_returned_non_json",
                message="Agent Context CLI did not return JSON in --json mode.",
                query=args.query,
                experts=experts,
                api_url=api_url,
                error=_sanitize_text(cli_result.stdout or cli_result.stderr, [token]),
            )
            _write_report(report_path, report)
            _print_status(report)
            return 1

        report = _build_pass_report(
            payload=payload,
            query=args.query,
            experts=experts,
            api_url=api_url,
            response_bytes=len(cli_result.stdout.encode("utf-8")),
        )
        _write_report(report_path, report)
        _print_status(report)
        return 0 if report["status"] == "passed" else 1
    finally:
        _stop_backend(process)


def _base_report(
    *,
    status: str,
    reason: str,
    message: str,
    query: str,
    experts: list[str],
    api_url: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "reason": reason,
        "message": message,
        "query": query,
        "experts": experts,
        "api_url": api_url,
        "generated_at_unix": int(time.time()),
    }
    if error:
        report["error"] = error[:2000]
    return report


def _build_pass_report(
    *,
    payload: dict[str, Any],
    query: str,
    experts: list[str],
    api_url: str,
    response_bytes: int,
) -> dict[str, Any]:
    if payload.get("mode") != "source_bundle":
        return _base_report(
            status="failed",
            reason="invalid_source_bundle_response",
            message="Agent Context CLI response must have mode='source_bundle'.",
            query=query,
            experts=experts,
            api_url=api_url,
        )

    selection_used = payload.get("selection_used")
    response_experts = payload.get("experts")
    pipeline_skipped = payload.get("pipeline_skipped")
    if not isinstance(selection_used, dict) or not isinstance(response_experts, list):
        return _base_report(
            status="failed",
            reason="invalid_source_bundle_response",
            message="Agent Context source_bundle response is missing selection_used or experts.",
            query=query,
            experts=experts,
            api_url=api_url,
        )
    if not isinstance(pipeline_skipped, list):
        return _base_report(
            status="failed",
            reason="invalid_source_bundle_response",
            message="Agent Context source_bundle response is missing pipeline_skipped.",
            query=query,
            experts=experts,
            api_url=api_url,
        )

    selected_source_counts = {
        str(expert.get("expert_id")): int(expert.get("selected_sources_count") or 0)
        for expert in response_experts
        if expert.get("expert_id")
    }

    return {
        "schema_version": 1,
        "status": "passed",
        "reason": "source_bundle_valid",
        "message": "Live local Agent Context smoke returned a valid source_bundle.",
        "query": payload.get("query") or query,
        "experts": [expert.get("expert_id") for expert in response_experts],
        "api_url": api_url,
        "selection_used": selection_used,
        "selected_source_counts": selected_source_counts,
        "response_bytes": response_bytes,
        "warnings": payload.get("warnings") or [],
        "pipeline_skipped": pipeline_skipped,
        "processing_time_ms": payload.get("processing_time_ms"),
        "generated_at_unix": int(time.time()),
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _print_status(report: dict[str, Any]) -> None:
    status = report.get("status", "unknown")
    reason = report.get("reason", "")
    message = report.get("message", "")
    print(f"Agent Context live smoke: {status} ({reason})")
    if message:
        print(message)


def _parse_experts(raw_experts: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_expert in raw_experts.split(","):
        expert = raw_expert.strip()
        if expert and expert not in seen:
            result.append(expert)
            seen.add(expert)
    return result


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_backend(port: int):
    env = os.environ.copy()
    env["PORT"] = str(port)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_health(base_url: str, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def _run_cli(
    *,
    query: str,
    experts: str,
    api_url: str,
    timeout_seconds: float,
):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.agent_context",
            "--query",
            query,
            "--experts",
            experts,
            "--api-url",
            api_url,
            "--timeout",
            str(timeout_seconds + CLI_TIMEOUT_GRACE_SECONDS),
            "--json",
        ],
        cwd=BACKEND_DIR,
        text=True,
        capture_output=True,
        timeout=timeout_seconds + CLI_TIMEOUT_GRACE_SECONDS + 10.0,
        check=False,
    )


def _classify_cli_failure(raw_error: str) -> tuple[str, str]:
    normalized = (raw_error or "").lower()
    if "http 413" in normalized or "exceeds configured max bytes" in normalized:
        return (
            "response_too_large",
            (
                "Agent Context API returned HTTP 413: source_bundle exceeded the "
                "configured response-size cap. Narrow the query/expert selection or "
                "raise AGENT_CONTEXT_MAX_RESPONSE_BYTES intentionally before rerunning."
            ),
        )
    if "http 504" in normalized or "exceeded configured timeout" in normalized:
        return (
            "api_timeout",
            (
                "Agent Context API returned HTTP 504: the live source_bundle request "
                "exceeded the configured timeout. Raise AGENT_CONTEXT_TIMEOUT_SECONDS "
                "or narrow the query/expert selection before rerunning."
            ),
        )
    return (
        "cli_failed",
        "Agent Context CLI returned a nonzero exit code.",
    )


def _stop_backend(process) -> None:
    if process is None:
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _sanitize_text(text: str, secrets: list[str]) -> str:
    sanitized = text or ""
    sanitized = re.sub(r"Bearer\s+\S+", "[redacted-token]", sanitized)
    sanitized = re.sub(r"\bBearer\b", "[redacted-token-label]", sanitized)
    sanitized = sanitized.replace("Authorization", "[redacted-header]")
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[redacted-secret]")
    return sanitized


if __name__ == "__main__":
    raise SystemExit(main())
