#!/usr/bin/env python3
"""Deterministic integrity check for an expert-scout run.

1. Citations: every source_key in the answer must exist in the corpus; every
   verbatim quote (>= 25 chars) must appear in the cited source (comments
   included, ellipsis-tolerant). No LLM is involved — LLM-based citation
   grading is unreliable (see docs/guides/expert-scout.md).
2. Tool loops: identical tool calls repeated back-to-back are flagged (a
   production failure mode: 94+ errors / 800 runs in the wild).

Usage:
  backend/.venv/bin/python backend/scripts/verify_citations.py \
      --answer run_dir/answer.md [--events run_dir/events.jsonl] [--json] [--annotate]

Exit codes: 0 = ok; 1 = hallucinated keys or tool loops; 2 = usage error.
--annotate prepends a "# WARNING: ..." line to the answer when problems found.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
HELPER = BACKEND_DIR / "scripts" / "expert_scout.py"
PY = BACKEND_DIR / ".venv" / "bin" / "python"

KEY_RE = re.compile(r"\b([a-z][a-z_]{2,}:\d+)\b")
QUOTE_RE = re.compile(r"[«\"']([^»\"']{25,300})[»\"']")
MIN_QUOTE = 25


def norm(text: str) -> str:
    text = text.replace("*", "").replace("_", " ")
    text = text.lower().replace("ё", "е")
    return re.sub(r"[\s\u00a0]+", " ", text)


def extract_keys(answer: str) -> list[str]:
    keys = []
    for key in KEY_RE.findall(answer):
        if not key.startswith("localhost:") and key not in keys:
            keys.append(key)
    return keys


def extract_quotes(answer: str) -> list[str]:
    return [q.strip() for q in QUOTE_RE.findall(answer) if len(q.strip()) >= MIN_QUOTE]


def fetch_sources(keys: list[str]) -> dict[str, str]:
    """source_key -> content + comments (via the read-only helper)."""
    out: dict[str, str] = {}
    for i in range(0, len(keys), 40):
        chunk = keys[i : i + 40]
        proc = subprocess.run(
            [str(PY), str(HELPER), "show", *chunk, "--comments-limit", "50", "--json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue
        for item in payload:
            if "error" in item:
                out[item["source_key"]] = ""
                continue
            comments = " ".join(c.get("text", "") for c in item.get("comments", []))
            out[item["source_key"]] = f"{item.get('content', '')} {comments}"
    return out


def quote_in_sources(quote: str, sources: dict[str, str]) -> str:
    fragments = [f for f in re.split(r"\s*(?:\.\.\.|…)\s*", quote) if f.strip()]
    long_frags = [f for f in fragments if len(f.strip()) >= MIN_QUOTE]
    if not long_frags:
        return "skipped"
    hay = norm(" ".join(sources.values()))
    hits = sum(1 for f in long_frags if norm(f) in hay)
    if hits == len(long_frags):
        return "ok"
    return "partial" if hits else "unverified"


def detect_loops(events_path: Path) -> list[dict]:
    if not events_path.exists():
        return []
    seen: dict[str, int] = {}
    loops = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        # tool_use = the request; "tool" events mirror results and would double-count
        if event.get("type") != "tool_use":
            continue
        part = event.get("part") or {}
        state = part.get("state") or {}
        name = part.get("tool") or "?"
        args = state.get("input") or part.get("args") or part.get("input") or {}
        args = json.dumps(args, sort_keys=True, ensure_ascii=False)
        sig = f"{name}::{args}"
        seen[sig] = seen.get(sig, 0) + 1
    for sig, count in seen.items():
        if count >= 3:
            name, _, args = sig.partition("::")
            loops.append({"tool": name, "calls": count, "args": args[:160]})
    return loops


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer", required=True)
    parser.add_argument("--events", help="events.jsonl for tool-loop detection")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--annotate", action="store_true", help="prepend WARNING to answer on problems")
    args = parser.parse_args()

    answer_path = Path(args.answer)
    if not answer_path.exists():
        print(f"error: answer not found: {answer_path}", file=sys.stderr)
        return 2
    answer = answer_path.read_text(encoding="utf-8")

    keys = extract_keys(answer)
    sources = fetch_sources(keys) if keys else {}
    missing_keys = sorted(k for k, content in sources.items() if not content.strip())
    quotes = extract_quotes(answer)
    quote_status = {q: quote_in_sources(q, sources) for q in quotes}
    unverified = sorted(q for q, st in quote_status.items() if st in ("unverified", "partial"))
    loops = detect_loops(Path(args.events)) if args.events else []

    report = {
        "answer": str(answer_path),
        "keys_total": len(keys),
        "keys_missing": missing_keys,
        "quotes_total": len(quotes),
        "quotes_unverified": unverified,
        "tool_loops": loops,
    }
    problems = bool(missing_keys or loops)
    summary = (
        f"# integrity: keys={len(keys)} missing={len(missing_keys)} "
        f"quotes={len(quotes)} unverified={len(unverified)} loops={len(loops)}"
    )
    print(summary, file=sys.stderr)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(summary)
        for key in missing_keys:
            print(f"  MISSING KEY: {key}")
        for loop in loops:
            print(f"  TOOL LOOP: {loop['tool']} x{loop['calls']} {loop['args']}")

    if problems and args.annotate:
        warnings = []
        if missing_keys:
            warnings.append(f"unverified source_keys: {', '.join(missing_keys)}")
        if loops:
            warnings.append(f"repeated tool calls: {', '.join(l['tool'] for l in loops)}")
        prefix = "# WARNING: " + "; ".join(warnings) + "\n\n"
        answer_path.write_text(prefix + answer, encoding="utf-8")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
