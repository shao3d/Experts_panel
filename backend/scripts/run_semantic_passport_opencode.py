#!/usr/bin/env python3
"""Run a prepared semantic passport packet through headless opencode serve.

Alternative to run_semantic_passport_vertex.py for environments where Vertex AI
is unavailable. Reads the same packet layout produced by
export_semantic_passport_packet.py /
export_semantic_passport_packet_from_telegram_json.py, sends the combined
prompt to the opencode serve HTTP API, and writes the same downstream
artifacts (raw text, parsed passport, validation, normalized passport,
receipt) so matrix comparison works unchanged.

Validation/normalization logic is reused from run_semantic_passport_vertex.py;
only the LLM call backend differs (serve sessions instead of generateContent).

Needs a running `opencode serve` (default http://127.0.0.1:4096) with access
to the requested model, e.g. opencode-go/muse-spark-1.3-contributor.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_semantic_passport_vertex import (  # noqa: E402
    normalize_passport,
    parse_generated_json,
    read_json,
    validate_passport,
    write_json,
)

DEFAULT_MODEL = "opencode-go/muse-spark-1.3-contributor"
DEFAULT_TIMEOUT_SECONDS = 900
SESSION_TITLE_PREFIX = "passport_"


def split_model(model_ref: str) -> tuple[str, str]:
    provider, _, model_id = model_ref.partition("/")
    if not provider or not model_id:
        raise SystemExit(f"Model must be 'provider/model', got '{model_ref}'")
    return provider, model_id


def assistant_text_from_message(message: dict[str, Any]) -> str:
    for part in reversed(message.get("parts") or []):
        if part.get("type") == "text" and (part.get("text") or "").strip():
            return str(part["text"]).strip()
    return ""


def message_error(message: dict[str, Any]) -> Optional[str]:
    err = (message.get("info") or {}).get("error")
    if not err:
        return None
    if isinstance(err.get("data"), dict):
        detail = err["data"].get("message", "")
    else:
        detail = ""
    return detail or str(err)


def text_from_messages_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = [m for m in payload if isinstance(m, dict)]
    else:
        return ""
    texts: list[str] = []
    for m in reversed(items):
        info = m.get("info") or {}
        role = info.get("role") or ("assistant" if "parts" in m else None)
        if role != "assistant":
            continue
        text = assistant_text_from_message(m)
        if text:
            texts.append(text)
    return texts[0] if texts else ""


def serve_post(url: str, payload: dict[str, Any], timeout: int) -> Any:
    response = requests.post(url, json=payload, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = {"raw_text": response.text}
    if response.ok:
        return body
    raise RuntimeError(
        f"opencode serve request failed status={response.status_code} "
        f"body={json.dumps(body, ensure_ascii=False)[:1000]}"
    )


def cleanup_session(base_url: str, session_id: Optional[str]) -> None:
    if not session_id:
        return
    for method, path in (("POST", f"/session/{session_id}/abort"),
                         ("DELETE", f"/session/{session_id}")):
        try:
            requests.request(method, f"{base_url}{path}", timeout=5)
        except Exception:
            pass


def run_passport_prompt(
    base_url: str,
    model_ref: str,
    system_text: str,
    user_prompt: str,
    timeout_seconds: int,
) -> tuple[str, Any]:
    """Send the passport prompt via serve. Returns (assistant_text, raw_reply)."""
    provider, model_id = split_model(model_ref)
    title = f"{SESSION_TITLE_PREFIX}{uuid.uuid4().hex[:12]}"
    session_id: Optional[str] = None
    try:
        created = serve_post(
            f"{base_url}/session",
            {"title": title, "model": {"providerID": provider, "id": model_id}},
            timeout=30,
        )
        session_id = created.get("id") if isinstance(created, dict) else None
        if not session_id:
            raise RuntimeError(f"session create returned no id: {str(created)[:300]}")

        reply = serve_post(
            f"{base_url}/session/{session_id}/message",
            {
                "model": {"providerID": provider, "modelID": model_id},
                "system": system_text,
                "parts": [{"type": "text", "text": user_prompt}],
            },
            timeout=timeout_seconds,
        )
        if isinstance(reply, dict):
            err = message_error(reply)
            if err:
                raise RuntimeError(f"opencode model error: {err[:500]}")
        text = text_from_messages_payload(reply)
        if not text:
            # Sync endpoint shape may vary between serve versions: fall back
            # to reading the session transcript once.
            try:
                transcript = requests.get(
                    f"{base_url}/session/{session_id}/message", timeout=30
                )
                if transcript.ok:
                    text = text_from_messages_payload(transcript.json())
            except Exception:
                pass
        if not text:
            raise RuntimeError("empty assistant response from opencode serve")
        return text, reply
    finally:
        cleanup_session(base_url, session_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a semantic passport packet through headless opencode serve."
    )
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--model",
        default=None,
        help=f"provider/model for serve (default: env OPENCODE_PASSPORT_MODEL or {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--serve-url",
        default=None,
        help="opencode serve base URL (default: env OPENCODE_URL or http://127.0.0.1:4096).",
    )
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--system-text", default=None)
    parser.add_argument("--count-only", action="store_true")
    parser.add_argument("--validate-existing", action="store_true")
    parser.add_argument("--normalize-existing", action="store_true")
    parser.add_argument("--normalized", action="store_true")
    return parser.parse_args()


def main() -> int:
    import os

    args = parse_args()
    model = args.model or os.getenv("OPENCODE_PASSPORT_MODEL", DEFAULT_MODEL)
    base_url = args.serve_url or os.getenv("OPENCODE_URL", "http://127.0.0.1:4096")

    packet_dir = args.packet_dir.resolve()
    manifest = read_json(packet_dir / "run_manifest.json")
    expert_id = manifest["corpus_stats"]["expert_id"]
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
        passport = read_json(output_dir / passport_name)
        validation = validate_passport(
            passport, source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        write_json(output_dir / f"{expert_id}_semantic_passport_validation.json", validation)
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0 if validation["valid_basic_contract"] else 2

    if args.normalize_existing:
        passport = read_json(output_dir / f"{expert_id}_semantic_passport.json")
        normalized = normalize_passport(
            passport, source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        normalized_path = output_dir / f"{expert_id}_semantic_passport.normalized.json"
        write_json(normalized_path, normalized)
        validation = validate_passport(
            normalized, source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        write_json(
            output_dir / f"{expert_id}_semantic_passport.normalized_validation.json",
            validation,
        )
        print(json.dumps(
            {"normalized_path": str(normalized_path), "validation": validation},
            ensure_ascii=False, indent=2,
        ))
        return 0 if validation["valid_basic_contract"] else 2

    receipt: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "opencode_serve",
        "packet_dir": str(packet_dir),
        "prompt_path": str(prompt_path),
        "model": model,
        "serve_url": base_url,
        "prompt_chars": len(prompt),
        "generate": None,
    }

    if args.count_only:
        receipt["status"] = "count_only"
        write_json(output_dir / f"{expert_id}_semantic_passport_receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0

    system_text = args.system_text or (
        "You are a precise evidence analyst. Return ONLY valid JSON conforming "
        "to the schema embedded in the user prompt. No markdown fences, "
        "no commentary outside the JSON."
    )
    generate_started_at = datetime.now(timezone.utc).isoformat()
    try:
        generated_text, raw_reply = run_passport_prompt(
            base_url, model, system_text, prompt, args.timeout_seconds
        )
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = str(exc)[:1000]
        write_json(output_dir / f"{expert_id}_semantic_passport_receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 2
    generate_finished_at = datetime.now(timezone.utc).isoformat()

    try:
        write_json(output_dir / f"{expert_id}_opencode_response.json", raw_reply)
    except (TypeError, ValueError):
        (output_dir / f"{expert_id}_opencode_response.txt").write_text(
            str(raw_reply)[:20000], encoding="utf-8"
        )
    (output_dir / f"{expert_id}_semantic_passport.raw.txt").write_text(
        generated_text, encoding="utf-8"
    )
    parsed_passport, parse_error = parse_generated_json(generated_text)
    validation = None
    if parsed_passport is not None:
        write_json(output_dir / f"{expert_id}_semantic_passport.json", parsed_passport)
        validation = validate_passport(
            parsed_passport, source_ref_index,
            expected_generated_at=manifest["created_at"],
        )
        write_json(
            output_dir / f"{expert_id}_semantic_passport_validation.json", validation
        )

    receipt["generate"] = {
        "started_at": generate_started_at,
        "finished_at": generate_finished_at,
        "text_chars": len(generated_text),
        "json_parse_error": parse_error,
        "validation": validation,
    }
    receipt["status"] = "generated" if parsed_passport is not None else "generated_unparsed"
    write_json(output_dir / f"{expert_id}_semantic_passport_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if parsed_passport is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
