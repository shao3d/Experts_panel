"""CLI wrapper for the explicit-only Agent Context API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

from .bootstrap import bootstrap_cli


DEFAULT_AGENT_CONTEXT_API_URL = "http://localhost:8000/api/v1/agent/context"
DEFAULT_TIMEOUT_SECONDS = 3600.0


class AgentContextCliError(Exception):
    """Expected CLI failure with a user-facing message."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call the Experts Panel Agent Context API.",
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Natural-language query to send to Experts Panel.",
    )

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--experts",
        help="Comma-separated expert_id list, for example: refat,akimov.",
    )
    selection.add_argument(
        "--group",
        choices=["tech", "tech_business"],
        help="Known expert group to query.",
    )

    parser.add_argument(
        "--recent",
        action="store_true",
        help="Restrict the backend source search to recent data.",
    )
    parser.add_argument(
        "--response-mode",
        choices=["source_bundle", "expert_digest"],
        default="source_bundle",
        help="API response mode. Defaults to source_bundle.",
    )
    parser.add_argument(
        "--api-url",
        help=(
            "Agent Context API URL. Defaults to AGENT_CONTEXT_API_URL or "
            f"{DEFAULT_AGENT_CONTEXT_API_URL}."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Request timeout in seconds. Defaults to AGENT_CONTEXT_TIMEOUT_SECONDS or 3600.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw API JSON instead of the summarized source bundle.",
    )
    return parser.parse_args(argv)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": args.query,
        "response_mode": args.response_mode,
        "expert_scope": "all",
        "expert_group": None,
        "expert_filter": None,
        "include_reddit": False,
        "include_main_source_comments": True,
        "include_drift_comment_groups": False,
        "synthesis_level": "none",
        "use_recent_only": bool(args.recent),
        "use_super_passport": True,
    }

    if args.experts:
        expert_ids = _parse_expert_ids(args.experts)
        if not expert_ids:
            raise AgentContextCliError("--experts must contain at least one expert_id")
        payload["expert_scope"] = "custom"
        payload["expert_filter"] = expert_ids
    elif args.group:
        payload["expert_scope"] = "group"
        payload["expert_group"] = args.group

    return payload


def call_agent_context_api(args: argparse.Namespace) -> dict[str, Any]:
    token = os.getenv("AGENT_CONTEXT_API_TOKEN")
    if not token:
        raise AgentContextCliError(
            "AGENT_CONTEXT_API_TOKEN is required for the Agent Context CLI"
        )

    api_url = (
        args.api_url
        or os.getenv("AGENT_CONTEXT_API_URL")
        or DEFAULT_AGENT_CONTEXT_API_URL
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
            f"Agent Context API request timed out after {timeout_seconds:g}s"
        ) from exc
    except requests.ConnectionError as exc:
        raise AgentContextCliError(
            f"Agent Context API endpoint is unreachable: {exc}"
        ) from exc
    except requests.HTTPError as exc:
        raise AgentContextCliError(_format_http_error(exc)) from exc
    except requests.RequestException as exc:
        raise AgentContextCliError(f"Agent Context API request failed: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise AgentContextCliError("Agent Context API returned non-JSON response") from exc


def print_summary(payload: dict[str, Any]) -> None:
    mode = payload.get("mode") or "source_bundle"
    print(f"Agent Context {mode}")
    print(f"request_id: {payload.get('request_id', '')}")
    print(f"query: {payload.get('query', '')}")
    print("selection_used:")
    for key, value in (payload.get("selection_used") or {}).items():
        print(f"  {key}: {_format_value(value)}")

    warnings = payload.get("warnings") or []
    print("warnings:")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - none")

    print("experts:")
    experts = payload.get("experts") or []
    if not experts:
        print("  - none")
    for expert in experts:
        expert_id = expert.get("expert_id", "")
        username = expert.get("channel_username", "")
        selected_count = expert.get("selected_sources_count", 0)
        no_results_reason = expert.get("no_results_reason")
        print(f"  - {expert_id} (@{username})")
        print(f"    selected_sources_count: {selected_count}")
        if no_results_reason:
            print(f"    no_results_reason: {no_results_reason}")

        if mode == "expert_digest":
            _print_expert_digest_summary(expert)
        else:
            _print_source_bundle_summary(expert)

    pipeline_used = payload.get("pipeline_used") or []
    pipeline_skipped = payload.get("pipeline_skipped") or []
    print("pipeline:")
    print(f"  used: {', '.join(pipeline_used) if pipeline_used else 'none'}")
    print(f"  skipped: {', '.join(pipeline_skipped) if pipeline_skipped else 'none'}")


def main(argv: list[str] | None = None, *, load_env: bool = True) -> int:
    if load_env:
        bootstrap_cli(__file__, logger_name="agent_context_cli")

    args = parse_args(argv)
    try:
        payload = call_agent_context_api(args)
    except AgentContextCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_summary(payload)
    return 0


def _parse_expert_ids(raw_experts: str) -> list[str]:
    expert_ids: list[str] = []
    seen: set[str] = set()
    for raw_expert_id in raw_experts.split(","):
        expert_id = raw_expert_id.strip()
        if expert_id and expert_id not in seen:
            expert_ids.append(expert_id)
            seen.add(expert_id)
    return expert_ids


def _print_source_bundle_summary(expert: dict[str, Any]) -> None:
    unattached_count = len(expert.get("unattached_linked_context") or [])
    print(f"    unattached_linked_context: {unattached_count}")

    main_sources = expert.get("main_sources") or []
    if not main_sources:
        print("    main_sources: none")
    for source in main_sources:
        source_id = source.get("telegram_message_id", "")
        relevance = source.get("relevance", "")
        reason = source.get("reason") or ""
        comments = source.get("comments") or {}
        author_count = len(comments.get("author_comments") or [])
        community_count = len(comments.get("community_comments") or [])
        linked_count = len(source.get("linked_context") or [])
        external_link_count = len(source.get("external_links") or [])

        print(f"    - {source_id} [{relevance}] {reason}")
        print(
            "      comments: "
            f"author={author_count} community={community_count}; "
            f"linked_context={linked_count}; "
            f"external_links={external_link_count}"
        )


def _print_expert_digest_summary(expert: dict[str, Any]) -> None:
    digest = expert.get("digest") or {}
    no_signal_reason = digest.get("no_signal_reason")
    if no_signal_reason:
        print(f"    digest.no_signal_reason: {no_signal_reason}")

    position = digest.get("position")
    if position:
        print(f"    position: {position}")

    source_refs = digest.get("source_refs") or []
    print(f"    source_refs: {len(source_refs)}")
    for source_ref in source_refs:
        source_key = source_ref.get("source_key", "")
        relevance = source_ref.get("relevance", "")
        reason = source_ref.get("reason") or ""
        comments_total = (
            int(source_ref.get("author_comments_count") or 0)
            + int(source_ref.get("community_comments_count") or 0)
        )
        print(f"    - {source_key} [{relevance}] {reason}")
        print(
            "      compact_counts: "
            f"comments={comments_total}; "
            f"linked_context={source_ref.get('linked_context_count', 0)}; "
            f"external_links={len(source_ref.get('external_links') or [])}"
        )

    key_signals = digest.get("key_signals") or []
    if key_signals:
        print("    key_signals:")
        for signal in key_signals:
            supporting_sources = signal.get("supporting_sources") or []
            print(
                "      - "
                f"[{signal.get('support_level', 'unknown')}] "
                f"{signal.get('claim', '')} "
                f"(sources: {', '.join(supporting_sources) or 'none'})"
            )
    else:
        print("    key_signals: none")

    comments = digest.get("comments_digest") or {}
    omitted_counts = digest.get("omitted_counts") or {}
    print(
        "    comments_digest: "
        f"author={comments.get('author_comments_count', 0)} "
        f"community={comments.get('community_comments_count', 0)} "
        f"included={len(comments.get('included_comments') or [])} "
        f"omitted={comments.get('omitted_comments_count', 0)}"
    )
    print(f"    omitted_counts: {_format_value(omitted_counts)}")


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


def _format_http_error(exc: requests.HTTPError) -> str:
    response = exc.response
    if response is None:
        return str(exc)

    message = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        message = str(body.get("message") or body.get("detail") or "")
    if not message:
        message = response.text or str(exc)
    return f"Agent Context API returned HTTP {response.status_code}: {message}"


def _format_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
