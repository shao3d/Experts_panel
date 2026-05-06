"""CLI wrapper for exact Agent Context source expansion."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

from .bootstrap import bootstrap_cli
from .agent_context import (
    AgentContextCliError,
    _format_evidence_quality,
    _format_http_error,
)


DEFAULT_AGENT_CONTEXT_EXPAND_API_URL = (
    "http://localhost:8000/api/v1/agent/context/expand"
)
DEFAULT_TIMEOUT_SECONDS = 3600.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expand exact Experts Panel Agent Context sources by source_key.",
    )
    parser.add_argument(
        "--source-keys",
        required=True,
        help="Comma-separated source_key list, for example: refat:101,etechlead:139.",
    )
    parser.add_argument(
        "--api-url",
        help=(
            "Agent Context expand API URL. Defaults to AGENT_CONTEXT_EXPAND_API_URL, "
            "derived AGENT_CONTEXT_API_URL, or localhost."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Request timeout in seconds. Defaults to AGENT_CONTEXT_TIMEOUT_SECONDS or 3600.",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=20000,
        help="Maximum characters of source content to return per source.",
    )
    parser.add_argument(
        "--max-comments-per-source",
        type=int,
        default=50,
        help="Maximum comments to return per source.",
    )
    parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Do not include direct comments under expanded sources.",
    )
    parser.add_argument(
        "--no-external-links",
        action="store_true",
        help="Do not include extracted external link references.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw API JSON instead of the summarized expansion.",
    )
    return parser.parse_args(argv)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_keys = _parse_source_keys(args.source_keys)
    if not source_keys:
        raise AgentContextCliError("--source-keys must contain at least one source_key")
    if args.max_content_chars <= 0:
        raise AgentContextCliError("--max-content-chars must be positive")
    if args.max_comments_per_source < 0:
        raise AgentContextCliError("--max-comments-per-source must be zero or positive")

    return {
        "source_keys": source_keys,
        "include_comments": not args.no_comments,
        "include_external_links": not args.no_external_links,
        "max_content_chars": args.max_content_chars,
        "max_comments_per_source": args.max_comments_per_source,
    }


def call_agent_context_expand_api(args: argparse.Namespace) -> dict[str, Any]:
    token = os.getenv("AGENT_CONTEXT_API_TOKEN")
    if not token:
        raise AgentContextCliError(
            "AGENT_CONTEXT_API_TOKEN is required for the Agent Context expand CLI"
        )

    api_url = (
        args.api_url
        or os.getenv("AGENT_CONTEXT_EXPAND_API_URL")
        or _derive_expand_url(os.getenv("AGENT_CONTEXT_API_URL"))
        or DEFAULT_AGENT_CONTEXT_EXPAND_API_URL
    )
    timeout_seconds = _resolve_timeout(args.timeout)
    payload = build_payload(args)

    try:
        response = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise AgentContextCliError(
            f"Agent Context expand API request timed out after {timeout_seconds:g}s"
        ) from exc
    except requests.ConnectionError as exc:
        raise AgentContextCliError(
            f"Agent Context expand API endpoint is unreachable: {exc}"
        ) from exc
    except requests.HTTPError as exc:
        raise AgentContextCliError(_format_http_error(exc)) from exc
    except requests.RequestException as exc:
        raise AgentContextCliError(
            f"Agent Context expand API request failed: {exc}"
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise AgentContextCliError(
            "Agent Context expand API returned non-JSON response"
        ) from exc


def print_summary(payload: dict[str, Any]) -> None:
    print("Agent Context source_expand")
    print(f"request_id: {payload.get('request_id', '')}")

    warnings = payload.get("warnings") or []
    print("warnings:")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - none")

    sources = payload.get("sources") or []
    print("sources:")
    if not sources:
        print("  - none")
    for source in sources:
        comments = source.get("comments") or {}
        truncation = source.get("truncation") or {}
        author_count = len(comments.get("author_comments") or [])
        community_count = len(comments.get("community_comments") or [])
        external_link_count = len(source.get("external_links") or [])
        print(
            f"  - {source.get('source_key', '')} "
            f"(@{source.get('channel_username', '')})"
        )
        quality = _format_evidence_quality(source)
        if quality:
            print(f"    {quality}")
        print(
            "    comments: "
            f"author={author_count} community={community_count}; "
            f"external_links={external_link_count}; "
            f"content_truncated={truncation.get('content_truncated', False)}; "
            f"comments_truncated={truncation.get('comments_truncated', False)}"
        )

    not_found = payload.get("not_found") or []
    print("not_found:")
    if not_found:
        for source_key in not_found:
            print(f"  - {source_key}")
    else:
        print("  - none")


def main(argv: list[str] | None = None, *, load_env: bool = True) -> int:
    if load_env:
        bootstrap_cli(__file__, logger_name="agent_context_expand_cli")

    args = parse_args(argv)
    try:
        payload = call_agent_context_expand_api(args)
    except AgentContextCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_summary(payload)
    return 0


def _parse_source_keys(raw_source_keys: str) -> list[str]:
    source_keys: list[str] = []
    seen: set[str] = set()
    for raw_source_key in raw_source_keys.split(","):
        source_key = raw_source_key.strip()
        if source_key and source_key not in seen:
            source_keys.append(source_key)
            seen.add(source_key)
    return source_keys


def _derive_expand_url(api_url: str | None) -> str | None:
    if not api_url:
        return None
    normalized = api_url.rstrip("/")
    if normalized.endswith("/context"):
        return f"{normalized}/expand"
    return api_url


def _resolve_timeout(cli_timeout: float | None) -> float:
    if cli_timeout is not None:
        if cli_timeout <= 0:
            raise AgentContextCliError("--timeout must be positive")
        return cli_timeout

    raw_timeout = os.getenv("AGENT_CONTEXT_TIMEOUT_SECONDS")
    if not raw_timeout:
        return DEFAULT_TIMEOUT_SECONDS

    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise AgentContextCliError(
            "AGENT_CONTEXT_TIMEOUT_SECONDS must be a number"
        ) from exc
    if timeout <= 0:
        raise AgentContextCliError("AGENT_CONTEXT_TIMEOUT_SECONDS must be positive")
    return timeout


if __name__ == "__main__":
    raise SystemExit(main())
