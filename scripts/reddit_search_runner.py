#!/usr/bin/env python3
"""Portable runner for the global reddit-search Codex skill.

This file intentionally uses only Python's standard library so the installer
can copy it to a user directory without installing packages. It calls only the
agent-facing Experts Panel API and never prints the bearer token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_API_URL = "https://expa.beyondhorizon.dev/api/v1/agent/reddit-search"
DEFAULT_TIMEOUT = 600.0


class RunnerError(Exception):
    """A safe, user-facing technical failure."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reddit-search",
        description="Run the Experts Panel Reddit Search V2 API from any directory.",
    )
    parser.add_argument("query", nargs="?", help="Reddit research question")
    parser.add_argument("--recent", action="store_true", help="Use only recent results")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--doctor", action="store_true", help="Check API health")
    parser.add_argument("--api-url", help="Override the Reddit Search API URL")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
    return parser.parse_args(argv)


def api_url(args: argparse.Namespace) -> str:
    return args.api_url or os.getenv("REDDIT_SEARCH_API_URL") or DEFAULT_API_URL


def timeout(args: argparse.Namespace) -> float:
    raw = args.timeout
    if raw is None:
        raw = os.getenv("REDDIT_SEARCH_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT))
    try:
        value = float(raw)
    except ValueError as exc:
        raise RunnerError(f"Invalid timeout: {raw!r}") from exc
    if value <= 0:
        raise RunnerError("Timeout must be positive")
    return value


def token() -> str:
    value = os.getenv("AGENT_CONTEXT_API_TOKEN", "").strip()
    if not value:
        raise RunnerError("AGENT_CONTEXT_API_TOKEN is required")
    return value


def request_json(url: str, *, method: str, payload: dict[str, Any] | None, bearer: str | None, timeout_s: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            detail = error_payload.get("message") or error_payload.get("detail") or "request failed"
        except (ValueError, UnicodeDecodeError):
            detail = "request failed"
        raise RunnerError(f"API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RunnerError(f"API unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RunnerError(f"API timed out after {timeout_s:g}s") from exc
    if status < 200 or status >= 300:
        raise RunnerError(f"API returned HTTP {status}")
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RunnerError("API returned non-JSON response") from exc


def doctor(args: argparse.Namespace) -> dict[str, Any]:
    url = api_url(args)
    base = url.rsplit("/api/", 1)[0]
    payload = request_json(f"{base}/health", method="GET", payload=None, bearer=None, timeout_s=min(timeout(args), 10.0))
    diagnostics = payload.get("diagnostics") or {}
    database = diagnostics.get("database") or {}
    return {
        "api_url": url,
        "health_status": payload.get("status", "unknown"),
        "database": database.get("status") or payload.get("database", "unknown"),
        "token_configured": bool(os.getenv("AGENT_CONTEXT_API_TOKEN", "").strip()),
    }


def search(args: argparse.Namespace) -> dict[str, Any]:
    return request_json(
        api_url(args),
        method="POST",
        payload={"query": args.query, "use_recent_only": bool(args.recent)},
        bearer=token(),
        timeout_s=timeout(args),
    )


def print_human(payload: dict[str, Any]) -> int:
    status = payload.get("status")
    if status == "completed":
        print(f"status: completed ({payload.get('found_count', 0)} posts kept)")
        print(payload.get("answer") or "")
        print("\nsources:")
        for source in payload.get("sources") or []:
            print(f"  - r/{source.get('subreddit', '?')}: {source.get('title', '')}")
            print(f"    {source.get('url', '')}")
        return 0
    if status == "abstained":
        print(f"status: abstained — {payload.get('message') or 'no reliable results'}")
        return 0
    print(f"status: {status or 'unknown'}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.doctor:
            report = doctor(args)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report.get("health_status") == "healthy" else 1
        if not args.query:
            raise RunnerError("query is required (or use --doctor)")
        payload = search(args)
    except RunnerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get("status") in {"completed", "abstained"} else 1
    return print_human(payload)


if __name__ == "__main__":
    sys.exit(main())
