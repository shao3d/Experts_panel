"""Helpers for parsing JSON returned by LLMs.

LLMs can still return fenced JSON, extra prose, escaped control characters, or
slightly truncated objects even when the provider is asked for JSON mode.
"""

import json
import re
from typing import Any, Iterable

from json_repair import repair_json


_FENCED_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def parse_llm_json(raw_content: str, *, context: str = "llm_json") -> Any:
    """Parse JSON-ish LLM output, repairing only when it contains JSON shape."""

    if raw_content is None:
        raise ValueError(f"{context}: empty LLM response")

    content = raw_content.strip()
    if not content:
        raise ValueError(f"{context}: empty LLM response")
    if "{" not in content and "[" not in content:
        preview = content[:500].replace("\n", "\\n")
        raise ValueError(f"{context}: no JSON object or array found; preview={preview!r}")

    last_error: Exception | None = None
    for candidate in _json_candidates(content):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    for candidate in _json_candidates(content):
        if "{" not in candidate and "[" not in candidate:
            continue
        try:
            repaired = repair_json(candidate)
            if repaired and repaired.strip():
                return json.loads(repaired)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc

    preview = content[:500].replace("\n", "\\n")
    if last_error is None:
        raise ValueError(f"{context}: no JSON object or array found; preview={preview!r}")
    raise ValueError(
        f"{context}: failed to parse LLM JSON: {last_error}; preview={preview!r}"
    ) from last_error


def _json_candidates(content: str) -> Iterable[str]:
    seen: set[str] = set()

    def emit(candidate: str):
        candidate = candidate.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            return candidate
        return None

    if candidate := emit(content):
        yield candidate

    for match in _FENCED_BLOCK_RE.finditer(content):
        if candidate := emit(match.group(1)):
            yield candidate

    for opener, closer in (("{", "}"), ("[", "]")):
        start = content.find(opener)
        end = content.rfind(closer)
        if start >= 0:
            if end > start:
                if candidate := emit(content[start : end + 1]):
                    yield candidate
            else:
                if candidate := emit(content[start:]):
                    yield candidate
