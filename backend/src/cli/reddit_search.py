"""CLI wrapper for the agent-facing Reddit Search V2 API.

Minimal, per docs/architecture/reddit-service.md (section "Agent-facing API"):

    reddit-search "What do practitioners say about Claude Code hooks?"
    reddit-search "o que mudou em LLMs locais" --recent
    reddit-search --json "query"
    reddit-search doctor

Contract:
- works from any project directory (no repo coupling beyond stdlib+requests);
- talks ONLY to the official API (POST /api/v1/agent/reddit-search);
- takes URL/token from env (REDDIT_SEARCH_API_URL / AGENT_CONTEXT_API_TOKEN);
- never prints the token;
- distinguishes completed / abstained / failed;
- nonzero exit code ONLY for real technical errors (network, 5xx, timeout,
  missing token). abstained is exit 0 with a human-readable message.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

from .bootstrap import bootstrap_cli

DEFAULT_REDDIT_SEARCH_API_URL = "http://localhost:8000/api/v1/agent/reddit-search"
DEFAULT_TIMEOUT_SECONDS = 600.0


class RedditSearchCliError(Exception):
    """Expected CLI failure with a user-facing message (technical error)."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reddit-search",
        description="Query the Experts Panel full Reddit Search V2 API.",
    )
    parser.add_argument("query", nargs="?", help="Query for the Reddit Search V2 pipeline.")
    parser.add_argument(
        "--recent",
        action="store_true",
        help="Hard-filter results to the recent window (use_recent_only=true).",
    )
    parser.add_argument(
        "--api-url",
        help=(
            "API base URL. Defaults to REDDIT_SEARCH_API_URL or "
            f"{DEFAULT_REDDIT_SEARCH_API_URL}."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Request timeout in seconds. Defaults to REDDIT_SEARCH_TIMEOUT_SECONDS or 600.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw API JSON (stable machine-readable mode).",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check reachability and auth (GET /health) without running a search.",
    )
    return parser.parse_args(argv)


def resolve_api_url(args: argparse.Namespace) -> str:
    return (
        args.api_url
        or os.getenv("REDDIT_SEARCH_API_URL")
        or DEFAULT_REDDIT_SEARCH_API_URL
    )


def resolve_timeout(args: argparse.Namespace) -> float:
    raw = args.timeout or os.getenv("REDDIT_SEARCH_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise RedditSearchCliError(f"Invalid timeout: {raw!r}") from exc
    if value <= 0:
        raise RedditSearchCliError("Timeout must be positive")
    return value


def _require_token() -> str:
    token = os.getenv("AGENT_CONTEXT_API_TOKEN")
    if not token:
        raise RedditSearchCliError(
            "AGENT_CONTEXT_API_TOKEN is required for the reddit-search CLI"
        )
    return token


def doctor(api_url: str, timeout_seconds: float) -> dict[str, Any]:
    """Check API reachability (no token needed for /health)."""
    base = api_url.rsplit("/api/", 1)[0]
    try:
        response = requests.get(f"{base}/health", timeout=min(timeout_seconds, 10.0))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise RedditSearchCliError(f"API unreachable: {exc}") from exc
    except ValueError as exc:
        raise RedditSearchCliError("API /health returned non-JSON") from exc
    return {
        "api_url": api_url,
        "health_status": payload.get("status", "unknown"),
        "database": (payload.get("diagnostics") or {}).get("database", {}).get("status")
        or payload.get("database", "unknown"),
        "token_configured": bool(os.getenv("AGENT_CONTEXT_API_TOKEN")),
    }


def call_reddit_search(args: argparse.Namespace) -> dict[str, Any]:
    token = _require_token()
    api_url = resolve_api_url(args)
    timeout_seconds = resolve_timeout(args)
    try:
        response = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": args.query,
                "use_recent_only": bool(args.recent),
            },
            timeout=timeout_seconds,
        )
    except requests.Timeout as exc:
        raise RedditSearchCliError(
            f"Reddit Search API timed out after {timeout_seconds:g}s"
        ) from exc
    except requests.ConnectionError as exc:
        raise RedditSearchCliError(f"Reddit Search API unreachable: {exc}") from exc
    except requests.RequestException as exc:
        raise RedditSearchCliError(f"Reddit Search API request failed: {exc}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("message") or response.text[:200]
        except ValueError:
            detail = response.text[:200]
        raise RedditSearchCliError(
            f"Reddit Search API returned {response.status_code}: {detail}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RedditSearchCliError("Reddit Search API returned non-JSON response") from exc


def print_summary(payload: dict[str, Any]) -> int:
    """Human-readable output. Returns process exit code."""
    status = payload.get("status")
    if status == "completed":
        print(f"status: completed ({payload.get('found_count', 0)} posts kept)")
        print(payload.get("answer") or "")
        print()
        print("sources:")
        for src in payload.get("sources") or []:
            print(f"  - r/{src.get('subreddit', '?')}: {src.get('title', '')}")
            print(f"    {src.get('url', '')}")
        return 0
    if status == "abstained":
        print(f"status: abstained — {payload.get('message') or 'no reliable results'}")
        return 0
    print(f"status: {status or 'unknown'}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None, *, load_env: bool = True) -> int:
    if load_env:
        bootstrap_cli(__file__, logger_name="reddit_search_cli")

    args = parse_args(argv)

    if args.doctor:
        try:
            report = doctor(resolve_api_url(args), resolve_timeout(args))
        except RedditSearchCliError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(report, indent=2))
        return 0 if report.get("health_status") == "healthy" else 1

    if not args.query:
        print("Error: query is required (or use --doctor)", file=sys.stderr)
        return 1

    try:
        payload = call_reddit_search(args)
    except RedditSearchCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    return print_summary(payload)


if __name__ == "__main__":
    sys.exit(main())
