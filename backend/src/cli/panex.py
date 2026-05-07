"""Production-safe portable runner for Панэкс / Agent Context API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
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
    _add_artifact_output_args(ask)
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
    _add_artifact_output_args(expand)
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

    read = subparsers.add_parser(
        "read",
        help="Read a saved Панэкс artifact without dumping the whole file.",
    )
    read.add_argument("--path", required=True, help="Path to a saved response.json.")
    read_mode = read.add_mutually_exclusive_group(required=True)
    read_mode.add_argument(
        "--manifest",
        action="store_true",
        help="Print a compact artifact manifest.",
    )
    read_mode.add_argument(
        "--expert",
        help="Print one expert slice from a saved expert_digest/source_bundle.",
    )
    read_mode.add_argument(
        "--source-key",
        help="Print one saved source entry by source_key.",
    )
    read.add_argument("--json", action="store_true", help="Print JSON.")

    cleanup = subparsers.add_parser(
        "cleanup",
        help="Delete old Панэкс artifacts from the artifact directory.",
    )
    cleanup.add_argument(
        "--ttl-days",
        type=float,
        help="Delete artifacts older than this many days. Defaults to PANEX_ARTIFACT_TTL_DAYS or 7.",
    )
    cleanup.add_argument("--json", action="store_true", help="Print JSON.")

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
            _validate_artifact_args(args)
            payload = call_ask_api(args)
            if _should_write_artifact(args):
                receipt = _write_artifact_response(
                    payload=payload,
                    args=args,
                    operation="ask",
                )
                _print_artifact_receipt(receipt, as_json=args.receipt_json)
            elif args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_context_summary(payload)
            return 0
        if args.command == "expand":
            _validate_artifact_args(args)
            payload = call_expand_api(args)
            if _should_write_artifact(args):
                receipt = _write_artifact_response(
                    payload=payload,
                    args=args,
                    operation="expand",
                    source_keys=build_expand_payload(args).get("source_keys") or [],
                )
                _print_artifact_receipt(receipt, as_json=args.receipt_json)
            elif args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_expand_summary(payload)
            return 0
        if args.command == "read":
            result = _read_artifact(args)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            else:
                _print_read_result(result)
            return 0
        if args.command == "cleanup":
            result = _cleanup_artifacts(args)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            else:
                _print_cleanup_result(result)
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


def _add_artifact_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the full API response to a new Панэкс artifact and print a receipt.",
    )
    parser.add_argument(
        "--receipt-json",
        action="store_true",
        help="Print the save receipt as compact JSON. Requires --save or --output.",
    )
    parser.add_argument(
        "--output",
        help="Save the full API response to this explicit JSON file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow --output to replace an existing file.",
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


def _validate_artifact_args(args: argparse.Namespace) -> None:
    if args.receipt_json and not _should_write_artifact(args):
        raise AgentContextCliError("--receipt-json requires --save or --output")
    if args.overwrite and not args.output:
        raise AgentContextCliError("--overwrite requires --output")
    if args.output:
        output_path = Path(args.output).expanduser()
        if output_path.exists() and not args.overwrite:
            raise AgentContextCliError(
                f"--output file already exists: {output_path}. Use --overwrite to replace it."
            )


def _should_write_artifact(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "save", False) or getattr(args, "output", None))


def _write_artifact_response(
    *,
    payload: dict[str, Any],
    args: argparse.Namespace,
    operation: str,
    source_keys: list[str] | None = None,
) -> dict[str, Any]:
    if args.output:
        response_path = Path(args.output).expanduser()
        response_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path = None
    else:
        artifact_dir = _new_artifact_dir(payload)
        response_path = artifact_dir / "response.json"
        receipt_path = artifact_dir / "receipt.json"

    _write_json_atomic(response_path, payload)
    response_bytes = response_path.stat().st_size
    receipt = _build_artifact_receipt(
        payload=payload,
        operation=operation,
        response_path=response_path,
        receipt_path=receipt_path,
        response_bytes=response_bytes,
        source_keys=source_keys or [],
    )
    if receipt_path is not None:
        _write_json_atomic(receipt_path, receipt)
    return receipt


def _build_artifact_receipt(
    *,
    payload: dict[str, Any],
    operation: str,
    response_path: Path,
    receipt_path: Path | None,
    response_bytes: int,
    source_keys: list[str],
) -> dict[str, Any]:
    mode = payload.get("mode")
    receipt: dict[str, Any] = {
        "kind": "panex_artifact",
        "operation": operation,
        "request_id": payload.get("request_id"),
        "mode": mode,
        "artifact_path": str(response_path),
        "receipt_path": str(receipt_path) if receipt_path else None,
        "response_bytes": response_bytes,
        "warnings": payload.get("warnings") or [],
        "read_next": [
            f"panex read --path {response_path} --manifest --json",
        ],
    }
    if payload.get("query") is not None:
        receipt["query"] = payload.get("query")
    experts = _expert_ids_from_payload(payload)
    if experts:
        receipt["experts"] = experts
        receipt["read_next"].append(
            f"panex read --path {response_path} --expert {experts[0]} --json"
        )
    if source_keys:
        receipt["source_keys"] = source_keys
        receipt["read_next"].append(
            f"panex read --path {response_path} --source-key {source_keys[0]} --json"
        )
    return receipt


def _new_artifact_dir(payload: dict[str, Any]) -> Path:
    now = datetime.now(timezone.utc)
    request_id = str(payload.get("request_id") or "no-request-id")
    safe_request_id = _safe_path_fragment(request_id)[:12] or "no-request-id"
    root = _artifact_root()
    artifact_dir = (
        root
        / now.strftime("%Y-%m-%d")
        / f"{now.strftime('%Y%m%dT%H%M%SZ')}-{safe_request_id}-{uuid.uuid4().hex[:8]}"
    )
    artifact_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    try:
        artifact_dir.chmod(0o700)
    except OSError:
        pass
    return artifact_dir


def _artifact_root() -> Path:
    configured = os.getenv("PANEX_ARTIFACT_DIR")
    root = Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "panex-artifacts"
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def _safe_path_fragment(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _read_artifact(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser()
    payload = _load_artifact_payload(path)
    if args.manifest:
        return _artifact_manifest(path, payload)
    if args.expert:
        expert = _find_expert(payload, args.expert)
        if expert is None:
            raise AgentContextCliError(f"expert not found in artifact: {args.expert}")
        return expert
    if args.source_key:
        source = _find_source_by_key(payload, args.source_key)
        if source is None:
            raise AgentContextCliError(f"source_key not found in artifact: {args.source_key}")
        return source
    raise AgentContextCliError("panex read requires --manifest, --expert, or --source-key")


def _load_artifact_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AgentContextCliError(f"artifact path does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentContextCliError(f"artifact is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AgentContextCliError(f"artifact root must be a JSON object: {path}")
    return payload


def _artifact_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    experts = _expert_ids_from_payload(payload)
    manifest: dict[str, Any] = {
        "kind": "panex_artifact_manifest",
        "artifact_path": str(path),
        "response_bytes": path.stat().st_size,
        "request_id": payload.get("request_id"),
        "mode": payload.get("mode"),
        "query": payload.get("query"),
        "warnings": payload.get("warnings") or [],
        "experts": experts,
        "expert_count": len(experts),
    }
    source_keys = _source_keys_from_payload(payload)
    if source_keys:
        manifest["source_keys_count"] = len(source_keys)
    return manifest


def _expert_ids_from_payload(payload: dict[str, Any]) -> list[str]:
    experts = payload.get("experts") or []
    if not isinstance(experts, list):
        return []
    result = []
    for expert in experts:
        if isinstance(expert, dict) and expert.get("expert_id"):
            result.append(str(expert["expert_id"]))
    return result


def _find_expert(payload: dict[str, Any], expert_id: str) -> dict[str, Any] | None:
    for expert in payload.get("experts") or []:
        if isinstance(expert, dict) and expert.get("expert_id") == expert_id:
            return expert
    return None


def _source_keys_from_payload(payload: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for source in _iter_sources(payload):
        source_key = source.get("source_key")
        if source_key:
            keys.append(str(source_key))
    return keys


def _find_source_by_key(payload: dict[str, Any], source_key: str) -> dict[str, Any] | None:
    for source in _iter_sources(payload):
        if source.get("source_key") == source_key:
            return source
    return None


def _iter_sources(payload: dict[str, Any]):
    for source in payload.get("sources") or []:
        if isinstance(source, dict):
            yield source
    for expert in payload.get("experts") or []:
        if not isinstance(expert, dict):
            continue
        for source in expert.get("main_sources") or []:
            if isinstance(source, dict):
                yield source
        digest = expert.get("digest") or {}
        if not isinstance(digest, dict):
            continue
        for field in ["source_refs", "source_index"]:
            for source in digest.get(field) or []:
                if isinstance(source, dict):
                    yield source


def _cleanup_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    root = _artifact_root()
    ttl_days = _resolve_cleanup_ttl(args.ttl_days)
    now = time.time()
    cutoff = now - ttl_days * 86400
    min_active_age_seconds = 3600
    deleted: list[str] = []
    skipped: list[str] = []

    for candidate in _iter_artifact_dirs(root):
        if candidate.name.endswith(".tmp") or (candidate / ".lock").exists():
            skipped.append(str(candidate))
            continue
        try:
            mtime = candidate.stat().st_mtime
        except OSError:
            skipped.append(str(candidate))
            continue
        if mtime >= cutoff or now - mtime < min_active_age_seconds:
            skipped.append(str(candidate))
            continue
        shutil.rmtree(candidate)
        deleted.append(str(candidate))

    return {
        "artifact_dir": str(root),
        "ttl_days": ttl_days,
        "deleted_count": len(deleted),
        "deleted": deleted,
        "skipped_count": len(skipped),
    }


def _iter_artifact_dirs(root: Path):
    if not root.exists():
        return
    for date_dir in root.iterdir():
        if not date_dir.is_dir():
            continue
        for candidate in date_dir.iterdir():
            if candidate.is_dir():
                yield candidate


def _resolve_cleanup_ttl(cli_ttl_days: float | None) -> float:
    if cli_ttl_days is not None:
        ttl_days = cli_ttl_days
    else:
        ttl_days = float(os.getenv("PANEX_ARTIFACT_TTL_DAYS", "7"))
    if ttl_days <= 0:
        raise AgentContextCliError("--ttl-days must be positive")
    return ttl_days


def _print_artifact_receipt(receipt: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")))
        return
    print("Panex artifact saved")
    print(f"request_id: {receipt.get('request_id')}")
    print(f"mode: {receipt.get('mode')}")
    print(f"artifact_path: {receipt.get('artifact_path')}")
    if receipt.get("receipt_path"):
        print(f"receipt_path: {receipt.get('receipt_path')}")
    print(f"response_bytes: {receipt.get('response_bytes')}")
    warnings = receipt.get("warnings") or []
    print(f"warnings: {warnings if warnings else 'none'}")
    print("read_next:")
    for command in receipt.get("read_next") or []:
        print(f"  {command}")


def _print_read_result(result: dict[str, Any]) -> None:
    if result.get("kind") == "panex_artifact_manifest":
        print("Panex artifact manifest")
        print(f"request_id: {result.get('request_id')}")
        print(f"mode: {result.get('mode')}")
        print(f"artifact_path: {result.get('artifact_path')}")
        print(f"response_bytes: {result.get('response_bytes')}")
        print(f"experts: {', '.join(result.get('experts') or []) or 'none'}")
        print(f"warnings: {result.get('warnings') or 'none'}")
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _print_cleanup_result(result: dict[str, Any]) -> None:
    print("Panex cleanup")
    print(f"artifact_dir: {result['artifact_dir']}")
    print(f"ttl_days: {result['ttl_days']}")
    print(f"deleted_count: {result['deleted_count']}")


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
  panex ask --query "Когда использовать subagents?" --experts refat,akimov --save --receipt-json
  panex ask --query "Что такое context rot?" --group tech_business --save --receipt-json
  panex ask --query "Что думают про LLM caching?" --all --save --receipt-json

Выбор экспертов:
  --experts refat,akimov       конкретные expert_id
  --group tech                 группа tech
  --group tech_business        группа Tech & Business
  --all                        все поддерживаемые эксперты

Режимы ответа:
  expert_digest                default: компактный digest для parent chat
  source_bundle                raw/audit режим, только явно:
    panex ask --query "..." --experts refat --response-mode source_bundle --save --receipt-json

Раскрытие источников после digest:
  panex expand --source-keys refat:238 --save --receipt-json
  panex expand --source-keys refat:238 --max-comments-per-source 3 --save --receipt-json

Artifact transport:
  --save --receipt-json сохраняет полный ответ вне текущего repo и печатает
  компактный receipt. Читать сохранённый ответ нужно через panex read:
    panex read --path <artifact_path> --manifest --json
    panex read --path <artifact_path> --expert refat --json
    panex read --path <artifact_path> --source-key refat:238 --json

Человеческие follow-up фразы:
  "раскрой по Рефату"
  "покажи источники"
  "дай пруфы"
  "что там в комментариях?"
  "самый спорный источник"

Диагностика:
  panex doctor
  panex doctor --live
  panex cleanup

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
