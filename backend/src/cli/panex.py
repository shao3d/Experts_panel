"""Production-safe portable runner for Панэкс / Agent Context API."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import requests

from .agent_context import (
    AgentContextCliError,
    _format_http_error,
    print_summary as print_context_summary,
)
from .agent_context_expand import (
    build_payload as build_expand_payload,
    print_summary as print_expand_summary,
)
from .bootstrap import bootstrap_cli, resolve_backend_dir


PRODUCTION_AGENT_CONTEXT_API_URL = (
    "https://experts-panel.fly.dev/api/v1/agent/context"
)
PRODUCTION_AGENT_CONTEXT_EXPAND_API_URL = (
    "https://experts-panel.fly.dev/api/v1/agent/context/expand"
)
LOCAL_AGENT_CONTEXT_API_URL = "http://localhost:8000/api/v1/agent/context"
LOCAL_AGENT_CONTEXT_EXPAND_API_URL = (
    "http://localhost:8000/api/v1/agent/context/expand"
)
DEFAULT_TIMEOUT_SECONDS = 3600.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="panex",
        description="Portable production-safe runner for Панэкс.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "guide",
        aliases=["help"],
        help="Print a human-friendly Панэкс usage guide without API calls.",
    )

    ask = subparsers.add_parser(
        "ask",
        help="Ask Experts Panel through production expert_digest by default.",
    )
    ask.add_argument("--query", required=True, help="Query to send to Панэкс.")
    ask.add_argument(
        "--response-mode",
        choices=["expert_digest", "source_bundle"],
        default="expert_digest",
        help="Response mode. Defaults to compact expert_digest.",
    )
    selection = ask.add_mutually_exclusive_group()
    selection.add_argument(
        "--experts",
        help="Comma-separated expert_id list, for example refat,akimov.",
    )
    selection.add_argument(
        "--group",
        choices=["tech", "tech_business"],
        help="Known expert group to query.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="Query all supported experts.",
    )
    _add_common_network_args(ask)
    ask.add_argument(
        "--recent",
        action="store_true",
        help="Restrict source search to recent data.",
    )

    expand = subparsers.add_parser(
        "expand",
        help="Expand exact source_key handles from a previous Панэкс digest.",
    )
    expand.add_argument(
        "--source-keys",
        required=True,
        help="Comma-separated source_key list, for example refat:239,akimov:201.",
    )
    _add_common_network_args(expand)
    expand.add_argument(
        "--max-content-chars",
        type=int,
        default=20000,
        help="Maximum characters of source content to return per source.",
    )
    expand.add_argument(
        "--max-comments-per-source",
        type=int,
        default=50,
        help="Maximum comments to return per source.",
    )
    expand.add_argument(
        "--no-comments",
        action="store_true",
        help="Do not include direct comments under expanded sources.",
    )
    expand.add_argument(
        "--no-external-links",
        action="store_true",
        help="Do not include author-supplied external link references.",
    )

    doctor = subparsers.add_parser(
        "doctor",
        help="Check portable Панэкс runner setup without printing secrets.",
    )
    doctor.add_argument(
        "--live",
        action="store_true",
        help="Also make a tiny production API request using AGENT_CONTEXT_API_TOKEN.",
    )
    doctor.add_argument(
        "--timeout",
        type=float,
        help="Live request timeout in seconds. Defaults to 3600.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print doctor result as JSON.",
    )
    return parser.parse_args(argv)


def build_ask_payload(args: argparse.Namespace) -> dict[str, Any]:
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
        expert_ids = _parse_csv(args.experts)
        if not expert_ids:
            raise AgentContextCliError("--experts must contain at least one expert_id")
        payload["expert_scope"] = "custom"
        payload["expert_filter"] = expert_ids
    elif args.group:
        payload["expert_scope"] = "group"
        payload["expert_group"] = args.group
    elif args.all:
        payload["expert_scope"] = "all"

    return payload


def call_ask_api(args: argparse.Namespace) -> dict[str, Any]:
    return _post_json(
        api_url=_resolve_api_url(
            args,
            production_url=PRODUCTION_AGENT_CONTEXT_API_URL,
            local_url=LOCAL_AGENT_CONTEXT_API_URL,
        ),
        payload=build_ask_payload(args),
        timeout_seconds=_resolve_timeout(args.timeout),
        error_prefix="Panex ask",
    )


def call_expand_api(args: argparse.Namespace) -> dict[str, Any]:
    return _post_json(
        api_url=_resolve_api_url(
            args,
            production_url=PRODUCTION_AGENT_CONTEXT_EXPAND_API_URL,
            local_url=LOCAL_AGENT_CONTEXT_EXPAND_API_URL,
        ),
        payload=build_expand_payload(args),
        timeout_seconds=_resolve_timeout(args.timeout),
        error_prefix="Panex expand",
    )


def run_doctor(args: argparse.Namespace, *, current_file: str | Path) -> dict[str, Any]:
    backend_dir = resolve_backend_dir(current_file)
    token_configured = bool(os.getenv("AGENT_CONTEXT_API_TOKEN"))
    global_command = shutil.which("panex")
    result: dict[str, Any] = {
        "status": "passed",
        "backend_dir": str(backend_dir),
        "cwd": os.getcwd(),
        "global_command": global_command,
        "token_configured": token_configured,
        "production_api_url": PRODUCTION_AGENT_CONTEXT_API_URL,
        "production_expand_api_url": PRODUCTION_AGENT_CONTEXT_EXPAND_API_URL,
        "warnings": [],
    }

    if not token_configured:
        result["status"] = "failed"
        result["warnings"].append(
            "missing AGENT_CONTEXT_API_TOKEN; configure the production token before live Панэкс calls"
        )

    if not global_command:
        result["warnings"].append(
            "global `panex` command is not on PATH; run scripts/install_panex_runner.sh"
        )

    if args.live and token_configured:
        try:
            payload = _post_json(
                api_url=PRODUCTION_AGENT_CONTEXT_API_URL,
                payload={
                    "query": "panex doctor smoke",
                    "response_mode": "expert_digest",
                    "expert_scope": "custom",
                    "expert_group": None,
                    "expert_filter": ["refat"],
                    "include_reddit": False,
                    "include_main_source_comments": True,
                    "include_drift_comment_groups": False,
                    "synthesis_level": "none",
                    "use_recent_only": True,
                    "use_super_passport": True,
                },
                timeout_seconds=_resolve_timeout(args.timeout),
                error_prefix="Panex doctor live",
            )
            result["live"] = {
                "mode": payload.get("mode"),
                "warnings": payload.get("warnings") or [],
                "experts_count": len(payload.get("experts") or []),
            }
        except AgentContextCliError as exc:
            result["status"] = "failed"
            result["warnings"].append(str(exc))
    elif args.live:
        result["status"] = "failed"
        result["warnings"].append("live doctor skipped because token is missing")

    return result


def main(argv: list[str] | None = None, *, load_env: bool = True) -> int:
    if load_env:
        bootstrap_cli(__file__, logger_name="panex_cli")

    args = parse_args(argv)
    try:
        if args.command in {"guide", "help"}:
            _print_guide()
            return 0
        if args.command == "ask":
            payload = call_ask_api(args)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_context_summary(payload)
            return 0
        if args.command == "expand":
            payload = call_expand_api(args)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_expand_summary(payload)
            return 0
        if args.command == "doctor":
            result = run_doctor(args, current_file=__file__)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                _print_doctor(result)
            return 0 if result["status"] == "passed" else 1
    except AgentContextCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Error: unknown panex command {args.command}", file=sys.stderr)
    return 2


def _add_common_network_args(parser: argparse.ArgumentParser) -> None:
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--api-url",
        help="Explicit API URL. Without this, panex uses Fly.io production.",
    )
    target.add_argument(
        "--local",
        action="store_true",
        help="Use localhost for explicit local backend debugging.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Request timeout in seconds. Defaults to 3600.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw API JSON.",
    )


def _post_json(
    *,
    api_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    error_prefix: str,
) -> dict[str, Any]:
    token = os.getenv("AGENT_CONTEXT_API_TOKEN")
    if not token:
        raise AgentContextCliError(
            "AGENT_CONTEXT_API_TOKEN is required for panex production calls. "
            "Configure the production token in the current environment."
        )

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
            f"{error_prefix} request timed out after {timeout_seconds:g}s"
        ) from exc
    except requests.ConnectionError as exc:
        raise AgentContextCliError(f"{error_prefix} endpoint is unreachable: {exc}") from exc
    except requests.HTTPError as exc:
        raise AgentContextCliError(_format_http_error(exc)) from exc
    except requests.RequestException as exc:
        raise AgentContextCliError(f"{error_prefix} request failed: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise AgentContextCliError(f"{error_prefix} returned non-JSON response") from exc


def _resolve_api_url(
    args: argparse.Namespace,
    *,
    production_url: str,
    local_url: str,
) -> str:
    if getattr(args, "api_url", None):
        return args.api_url
    if getattr(args, "local", False):
        return local_url
    return production_url


def _resolve_timeout(cli_timeout: float | None) -> float:
    if cli_timeout is None:
        return DEFAULT_TIMEOUT_SECONDS
    if cli_timeout <= 0:
        raise AgentContextCliError("--timeout must be positive")
    return cli_timeout


def _parse_csv(raw_value: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_value.split(","):
        item = raw_item.strip()
        if item and item not in seen:
            values.append(item)
            seen.add(item)
    return values


def _print_doctor(result: dict[str, Any]) -> None:
    print("Panex doctor")
    print(f"status: {result['status']}")
    print(f"backend_dir: {result['backend_dir']}")
    print(f"global_command: {result.get('global_command') or 'not found'}")
    print(f"token_configured: {result['token_configured']}")
    print(f"production_api_url: {result['production_api_url']}")
    print(f"production_expand_api_url: {result['production_expand_api_url']}")
    warnings = result.get("warnings") or []
    print("warnings:")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - none")


def _print_guide() -> None:
    print(
        """Panex guide

Что это:
  Панэкс - явный помощник для запросов к Experts Panel на Fly.io.
  Он приносит practitioner-opinion signals из постов экспертов, direct comments
  под выбранными источниками, source_key handles и evidence_quality calibration.

Главное правило:
  Панэкс не запускается автоматически. Используй явный запрос:
    "Спроси Панэкс ..."
    "Панэкс, узнай ..."
    "Вызови experts_panel_researcher ..."

Обычный поиск:
  panex ask --query "Когда использовать subagents?" --experts refat,akimov --json
  panex ask --query "Что такое context rot?" --group tech_business --json
  panex ask --query "Что думают про LLM caching?" --all --json

Выбор экспертов:
  --experts refat,akimov       конкретные expert_id
  --group tech                 группа tech
  --group tech_business        группа Tech & Business
  --all                        все поддерживаемые эксперты

Режимы ответа:
  expert_digest                default: компактный digest для parent chat
  source_bundle                raw/audit режим, только явно:
    panex ask --query "..." --experts refat --response-mode source_bundle --json

Раскрытие источников после digest:
  panex expand --source-keys refat:238 --json
  panex expand --source-keys refat:238 --max-comments-per-source 3 --json

Человеческие follow-up фразы:
  "раскрой по Рефату"
  "покажи источники"
  "дай пруфы"
  "что там в комментариях?"
  "самый спорный источник"

Диагностика:
  panex doctor
  panex doctor --live

Границы:
  - production default: https://experts-panel.fly.dev
  - localhost только явно через --local или --api-url
  - external links не открываются и не суммаризируются автоматически
  - drift comment groups не выбираются в agent API default
  - token нужен для live calls, но не печатается и не хранится в shim
"""
    )


if __name__ == "__main__":
    raise SystemExit(main())
