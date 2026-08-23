#!/usr/bin/env python3
"""Headless opencode client for drift analysis.

Ports the Live Navigator ingestion pattern to Experts Panel:
task file -> `opencode run --attach` -> poll session by title -> strip JSON.

Contract matches DriftSchedulerService.analyze_drift_async():
analyze(post_text, comments) -> dict  with keys has_drift/confidence/drift_topics.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OPENCODE_URL = os.getenv("OPENCODE_URL", "http://127.0.0.1:4096")
OPENCODE_BIN = os.getenv("OPENCODE_BIN", "/home/ubuntu/.opencode/bin/opencode")
OPENCODE_MODEL = os.getenv("OPENCODE_DRIFT_MODEL", "opencode/x-preview-f-free")
DRIFT_AGENT = os.getenv("OPENCODE_DRIFT_AGENT", "drift")
TASK_DIR = os.getenv("OPENCODE_TASK_DIR", "/tmp/drift_task")
POLL_INTERVAL = float(os.getenv("OPENCODE_POLL_INTERVAL", "3"))
RUN_TIMEOUT_S = int(os.getenv("OPENCODE_RUN_TIMEOUT_S", "420"))
FETCH_DEADLINE_S = int(os.getenv("OPENCODE_FETCH_DEADLINE_S", "90"))
RETRY_BACKOFF = [int(x) for x in os.getenv(
    "OPENCODE_RETRY_BACKOFF", "15,30,60").split(",")]
BATCH_SIZE = int(os.getenv("OPENCODE_DRIFT_BATCH_SIZE", "12"))


def build_prompt(post_text: str, comments: List[Dict[str, str]]) -> str:
    """Same prompt text as DriftSchedulerService.analyze_drift_async."""
    comments_text = "\n".join([f"- {c['author']}: {c['text']}" for c in comments])

    return f"""Analyze this Telegram post and its comments to determine if the discussion DRIFTED to other topics.

POST (anchor):
{post_text[:1000]}...

COMMENTS:
{comments_text[:3000]}

TASK:
1. Determine if comments discuss topics NOT mentioned in the post
2. If yes (drift detected), extract drift topics with:
   - topic: General theme (1-2 sentences)
   - keywords: Specific terms, technologies, names (array)
   - key_phrases: Direct quotes from comments (array, 1-3 phrases)
   - context: Brief explanation (1 sentence)

CRITERIA FOR DRIFT:
✅ DRIFT:
- Comments ask about/discuss technologies/concepts not in post
- Discussion moves to different subject area
- New specific questions with detailed answers

❌ NOT DRIFT:
- Comments just expand on post topic
- Questions clarifying post content
- Generic reactions/thanks

CONFIDENCE:
- high: Clear drift, obvious new topics
- medium: Partial drift, some new elements
- low: Unclear if drift or just expansion

Return ONLY valid JSON:
{{
  "has_drift": true/false,
  "confidence": "high|medium|low",
  "drift_topics": [
    {{
      "topic": "...",
      "keywords": ["..."],
      "key_phrases": ["..."],
      "context": "..."
    }}
  ] or null
}}"""


def _strip_json_markdown(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.lstrip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
        if t.endswith("```"):
            t = t[:-3].strip()
    return t


def _extract_json(text_response: str) -> Dict[str, Any]:
    """Robust extraction mirroring DriftSchedulerService heuristics."""
    try:
        parsed = json.loads(_strip_json_markdown(text_response))
    except json.JSONDecodeError:
        idx_brace = text_response.find("{")
        idx_bracket = text_response.find("[")
        start_idx, end_idx = -1, -1
        if idx_brace != -1 and idx_bracket != -1:
            if idx_brace < idx_bracket:
                start_idx, end_idx = idx_brace, text_response.rfind("}")
            else:
                start_idx, end_idx = idx_bracket, text_response.rfind("]")
        elif idx_brace != -1:
            start_idx, end_idx = idx_brace, text_response.rfind("}")
        elif idx_bracket != -1:
            start_idx, end_idx = idx_bracket, text_response.rfind("]")
        if start_idx == -1 or end_idx <= start_idx:
            raise ValueError(f"No valid JSON in response: {text_response[:120]}")
        parsed = json.loads(text_response[start_idx:end_idx + 1])

    # Mirror scheduler normalization: bare list -> first dict element
    if isinstance(parsed, list):
        if parsed and isinstance(parsed[0], dict):
            return parsed[0]
        raise ValueError(f"Invalid list structure: {str(parsed)[:120]}")
    if not isinstance(parsed, dict):
        raise ValueError(f"Non-dict JSON: {type(parsed)}")
    return parsed


def _session_id_by_title(title: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "5", f"{OPENCODE_URL}/session"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        for s in json.loads(out):
            if s.get("title") == title:
                return s.get("id")
    except Exception:
        return None
    return None


def _fetch_assistant_text(session_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (text, error). Mirrors live-navigator fetch_messages."""
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             f"{OPENCODE_URL}/session/{session_id}/message"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        msgs = json.loads(out)
    except Exception as e:
        return None, f"fetch failed: {e}"

    last_text = None
    for m in msgs:
        info = m.get("info", {})
        if info.get("role") != "assistant":
            continue
        err = info.get("error")
        if err:
            detail = err.get("data", {}).get("message", "") if isinstance(err.get("data"), dict) else str(err)
            return None, detail or str(err)
        for p in reversed(m.get("parts", [])):
            if p.get("type") == "text" and p.get("text", "").strip():
                last_text = p["text"]
    return last_text, None


def _run_once(post_text: str, comments: List[Dict[str, str]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One attempt: attach run + poll. Returns (parsed_dict, error)."""
    os.makedirs(TASK_DIR, exist_ok=True)
    title = f"drift_{uuid.uuid4().hex[:12]}"
    task_path = os.path.join(TASK_DIR, f"{title}.txt")

    with open(task_path, "w", encoding="utf-8") as f:
        f.write(build_prompt(post_text, comments))

    cmd = (
        f'export PATH="$PATH:$HOME/.opencode/bin" && '
        f"{OPENCODE_BIN} run --attach {OPENCODE_URL} "
        f"--model {OPENCODE_MODEL} --agent {DRIFT_AGENT} "
        f"--title {title} "
        f"'Выполни анализ дрейфа из прикреплённого файла. Верни ТОЛЬКО валидный JSON.' "
        f"--file {task_path}"
    )
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True,
            timeout=RUN_TIMEOUT_S + 30,
        )
        if proc.returncode != 0:
            return None, (proc.stderr or proc.stdout or "run failed").strip()[:300]
    except subprocess.TimeoutExpired:
        return None, f"run timeout after {RUN_TIMEOUT_S + 30}s"

    # Attach client does not print the final answer; poll the API by title.
    deadline = time.time() + FETCH_DEADLINE_S
    while time.time() < deadline:
        sid = _session_id_by_title(title)
        if sid:
            text, err = _fetch_assistant_text(sid)
            if text or err:
                break
        time.sleep(POLL_INTERVAL)
    else:
        return None, f"no answer within {FETCH_DEADLINE_S}s"

    try:
        os.remove(task_path)
    except OSError:
        pass

    if err or not text:
        return None, err or "empty response"

    try:
        result = _extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return None, f"invalid JSON: {e}"
    return result, None


def build_batch_prompt(groups: List[Dict[str, Any]]) -> str:
    parts = [
        f"Analyze {len(groups)} Telegram posts with their comments. "
        f"For EACH group independently determine whether the comment discussion DRIFTED "
        f"to topics NOT present in its own post."
    ]
    for g in groups:
        comments_text = "\n".join(
            f"- {c['author']}: {c['text']}" for c in g.get("comments") or [])
        parts.append(
            f"\n=== GROUP post_id={g['post_id']} ===\n"
            f"POST:\n{(g.get('post_text') or '')[:700]}\n\n"
            f"COMMENTS:\n{comments_text[:1800]}"
        )
    parts.append(
        "\n=== TASK ===\n"
        "For each group apply these criteria:\n"
        "✅ DRIFT: comments discuss technologies/concepts not in that group's post; "
        "discussion moves to another subject area; new specific questions with detailed answers\n"
        "❌ NOT DRIFT: clarifications of the post content, generic reactions/thanks\n"
        "confidence: high = clear drift, medium = partial, low = unclear\n\n"
        "If a topic is borderline or uncertain, STILL report it with confidence=\"low\" "
        "(coverage matters more than precision).\n\n"
        "Return ONLY a valid JSON array — one object per group, SAME ORDER as above, "
        "echoing post_id exactly:\n"
        '[{"post_id": 123, "has_drift": true, "confidence": "medium", '
        '"drift_topics": [{"topic": "...", "keywords": ["..."], "key_phrases": ["..."], '
        '"context": "..."}]}, ...]\n'
        "Use null for drift_topics when has_drift is false. No commentary outside the array."
    )
    return "\n".join(parts)


def analyze_batch(groups: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Analyze several groups in ONE opencode call.

    Returns {post_id: parsed_verdict}. Groups missing from the response are
    simply absent from the mapping — caller decides on individual retries.
    """
    os.makedirs(TASK_DIR, exist_ok=True)
    title = f"driftb_{uuid.uuid4().hex[:12]}"
    task_path = os.path.join(TASK_DIR, f"{title}.txt")

    with open(task_path, "w", encoding="utf-8") as f:
        f.write(build_batch_prompt(groups))

    cmd = (
        f'export PATH="$PATH:$HOME/.opencode/bin" && '
        f"{OPENCODE_BIN} run --attach {OPENCODE_URL} "
        f"--model {OPENCODE_MODEL} --agent {DRIFT_AGENT} "
        f"--title {title} "
        f"'Выполни пакетный анализ дрейфа из прикреплённого файла. Верни ТОЛЬКО валидный JSON-массив.' "
        f"--file {task_path}"
    )
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True,
            timeout=RUN_TIMEOUT_S + 30,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "run failed").strip()[:300])
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"batch run timeout after {RUN_TIMEOUT_S + 30}s")

    deadline = time.time() + FETCH_DEADLINE_S
    text, err = None, None
    while time.time() < deadline:
        sid = _session_id_by_title(title)
        if sid:
            text, err = _fetch_assistant_text(sid)
            if text or err:
                break
        time.sleep(POLL_INTERVAL)

    try:
        os.remove(task_path)
    except OSError:
        pass

    if err or not text:
        raise RuntimeError(err or "empty response")

    # Expect a JSON array; tolerate a bare object when only one group asked.
    stripped = _strip_json_markdown(text)
    parsed = None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        arr_start = stripped.find("[")
        arr_end = stripped.rfind("]")
        obj_start = stripped.find("{")
        if arr_start != -1 and arr_end > arr_start:
            parsed = json.loads(stripped[arr_start:arr_end + 1])
        elif obj_start != -1:
            obj_end = stripped.rfind("}")
            parsed = json.loads(stripped[obj_start:obj_end + 1])
        else:
            raise ValueError(f"No JSON in batch response: {stripped[:150]}")

    by_pid: Dict[int, Dict[str, Any]] = {}
    items = parsed if isinstance(parsed, list) else (
        parsed.get("results") or parsed.get("items") or [])
    if isinstance(items, dict) and len(groups) == 1:
        items = [items]
    for item in items:
        if not isinstance(item, dict) or "post_id" not in item:
            continue
        try:
            pid = int(item["post_id"])
        except (TypeError, ValueError):
            continue
        if "has_drift" not in item:
            continue
        by_pid[pid] = item
    if not by_pid:
        raise ValueError(f"Batch response contained no usable verdicts: {str(parsed)[:200]}")
    return by_pid


def analyze(post_text: str, comments: List[Dict[str, str]]) -> Dict[str, Any]:
    """Analyze one group with retries/backoff. Raises on final failure."""
    last_err = None
    for attempt in range(len(RETRY_BACKOFF) + 1):
        result, err = _run_once(post_text, comments)
        if result is not None:
            return result
        last_err = err
        logger.warning("opencode drift attempt %d/%d failed: %s",
                       attempt + 1, len(RETRY_BACKOFF) + 1, str(err)[:150])
        if attempt < len(RETRY_BACKOFF):
            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
    raise RuntimeError(f"opencode drift failed after retries: {last_err}")


def check_serve_health() -> bool:
    """True when the local opencode serve answers."""
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "5", f"{OPENCODE_URL}/session"],
            capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0 and out.stdout.strip().startswith("[")
    except Exception:
        return False
