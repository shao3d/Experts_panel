#!/usr/bin/env python3
"""Deterministic integrity check for an expert-scout run.

1. Citations: every source_key in the answer must exist in the corpus; every
   verbatim quote (>= 25 chars) must appear in its locally cited, fully read
   source (ordered ellipses supported). No LLM is involved — LLM-based citation
   grading is unreliable (see docs/guides/expert-scout.md).
2. Tool loops: identical tool calls repeated back-to-back are flagged (a
   production failure mode: 94+ errors / 800 runs in the wild).

Usage:
  backend/.venv/bin/python backend/scripts/verify_citations.py \
      --answer run_dir/answer.md [--events run_dir/events.jsonl] [--json] [--annotate]

Exit codes: 0 = verified; 1 = incomplete/unverified evidence; 2 = usage error.
--annotate prepends a "# WARNING: ..." line to the answer when problems found.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.scout_evidence import read_evidence, tool_calls, finished, sources_from_output

BACKEND_DIR = Path(__file__).resolve().parents[1]
HELPER = BACKEND_DIR / "scripts" / "expert_scout.py"
PY = BACKEND_DIR / ".venv" / "bin" / "python"

KEY_RE = re.compile(r"\b([a-z][a-z_]{2,}:\d+)\b")
QUOTE_RE = re.compile(r'«([^»]{25,})»|“([^”]{25,})”|"([^"\n]{25,})"')
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
    return [next(q for q in match.groups() if q is not None).strip() for match in QUOTE_RE.finditer(answer)]


def primary_text(text: str) -> str:
    """Video TITLE/SUMMARY are metadata and synthesis, not verbatim speech."""
    return text.partition("\nCONTENT:\n")[2] if "\nCONTENT:\n" in text else text


def fetch_sources(keys: list[str]) -> dict[str, str]:
    """Fail closed if a source lookup cannot be completed."""
    out: dict[str, str] = {key: "" for key in keys}
    for i in range(0, len(keys), 3):
        chunk = keys[i : i + 3]
        proc = subprocess.run(
            [str(PY), str(HELPER), "show", *chunk, "--comments-limit", "0", "--json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode:
            raise RuntimeError(f"source lookup failed (exit {proc.returncode})")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError("source lookup returned invalid JSON") from None
        if not isinstance(payload, list):
            raise RuntimeError("source lookup returned invalid payload")
        returned = set()
        for item in payload:
            if not isinstance(item, dict) or item.get("source_key") not in chunk:
                raise RuntimeError("source lookup returned an unexpected key")
            returned.add(item["source_key"])
            if "error" in item:
                out[item["source_key"]] = ""
                continue
            out[item["source_key"]] = item.get("content", "")
        if returned != set(chunk):
            raise RuntimeError("source lookup omitted a requested key")
    return out


def quote_in_sources(quote: str, sources: dict[str, str]) -> str:
    fragments = [f for f in re.split(r"\s*(?:\.\.\.|…)\s*", quote) if f.strip()]
    if len(quote.strip()) < MIN_QUOTE:
        return "skipped"
    # All fragments must occur in order in a single source. Concatenating
    # sources previously allowed quotations assembled from unrelated posts.
    for text in sources.values():
        hay = norm(primary_text(text))
        cursor = 0
        for fragment in fragments:
            if not fragment.strip():
                continue
            position = hay.find(norm(fragment), cursor)
            if position < 0:
                break
            cursor = position + len(norm(fragment))
        else:
            return "ok"
    return "unverified"


def bound_quote_status(answer: str, sources: dict[str, str], reads: dict | None = None) -> dict[str, str]:
    results = {}
    for match in QUOTE_RE.finditer(answer):
        quote = next(q for q in match.groups() if q is not None).strip()
        boundary = answer.rfind("\n\n", 0, match.start())
        start = boundary + 2 if boundary >= 0 else 0
        end = answer.find("\n\n", match.end())
        end = len(answer) if end < 0 else end
        # A Markdown table row carries its own citation. A key in the next
        # row can be closer on the page without being the quote's source.
        line_start = answer.rfind("\n", 0, match.start()) + 1
        line_end = answer.find("\n", match.end())
        line_end = len(answer) if line_end < 0 else line_end
        if answer[line_start:line_end].strip().startswith('|'):
            start, end = line_start, line_end
        else:
            # Adjacent Markdown list items are separate citation scopes even
            # without blank lines; indented continuation belongs to its item.
            items = list(re.finditer(r'(?m)^[ \t]*(?:[-+*]|\d+[.)])[ \t]+', answer[start:end]))
            preceding = [item for item in items if start + item.start() <= match.start()]
            if preceding:
                item_start = start + preceding[-1].start()
                following = [start + item.start() for item in items
                             if start + item.start() > match.end()]
                end = following[0] if following else end
                start = item_start
        candidates = list(KEY_RE.finditer(answer, start, end))
        if not candidates:
            results[quote] = "unbound"
            continue
        nearest = min(candidates, key=lambda k: min(abs(k.start()-match.end()), abs(k.end()-match.start())))
        key = nearest.group(1)
        evidence = sources.get(key, "")
        if reads and re.search(r'комментар|comment|reply',answer[start:end],re.I):
            evidence = "\n".join(c.get('text','') for c in reads.get(key,{}).get('comments',[]) if c.get('is_author'))
        results[quote] = quote_in_sources(quote, {key: evidence})
    return results


def loops_in_events(events: list[dict]) -> list[dict]:
    seen = {}
    for call in tool_calls(events):
        signature = str(call['tool']) + '::' + json.dumps(call['args'],sort_keys=True,ensure_ascii=False)
        seen[signature] = seen.get(signature,0)+1
    loops = []
    for signature,count in seen.items():
        if count >= 3:
            name,_,args = signature.partition('::')
            loops.append({'tool':name,'calls':count,'args':args[:160]})
    return loops


def detect_loops(events_path: Path) -> list[dict]:
    if not events_path.exists():
        return []
    events = []
    for line in events_path.read_text(encoding='utf-8').splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return loops_in_events(events)


def assess_answer(answer: str, events: list[dict] | None = None, *, lookup_unread: bool = True) -> dict:
    keys = extract_keys(answer)
    reads = read_evidence(events or [])
    verification_error = None
    sources = {key: reads[key]['content'] for key in keys if key in reads}
    try:
        if lookup_unread:
            sources.update(fetch_sources([key for key in keys if key not in reads]))
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        verification_error = str(exc)
    missing = sorted(k for k in keys if not sources.get(k,'').strip()) if lookup_unread else []
    unread = sorted(k for k in keys if events is not None and k not in reads)
    incomplete = sorted(k for k in keys if k in reads and not reads[k]['fully_read'])
    quotes = extract_quotes(answer)
    statuses = bound_quote_status(answer,sources,reads)
    unverified = sorted(q for q,status in statuses.items() if status != 'ok')
    loops = loops_in_events(events or [])
    calls = tool_calls(events or [])
    completed = [c for c in calls if c['successful']]
    abstain = bool(re.search(r'не (?:наш[её]л|найден|удалось найти)|нет (?:сигнала|подтверждений)|not found|no signal',answer[:600],re.I))
    search_queries = {c['args'].get('query','').strip() for c in completed if c['args'].get('command')=='search'} - {''}
    protocol = abstain and len(search_queries)>=3 and any(c['args'].get('command')=='digest' for c in completed)
    uncited = not keys and not protocol
    unfinished = events is not None and not finished(events)
    problems = bool(missing or unread or incomplete or unverified or loops or verification_error or uncited or unfinished)
    return {'keys_total':len(keys),'keys_missing':missing,'keys_unread':unread,
            'keys_incomplete':incomplete,'quotes_total':len(quotes),'quotes_unverified':unverified,
            'tool_loops':loops,'verification_error':verification_error,'uncited_answer':uncited,
            'unfinished_run':unfinished,'status':'error' if verification_error else 'partial' if problems else 'completed'}


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

    events = None
    if args.events:
        try:
            events = [json.loads(line) for line in Path(args.events).read_text(encoding='utf-8').splitlines() if line.strip()]
            if any(not isinstance(event, dict) for event in events):
                raise ValueError('events must be objects')
        except (OSError, ValueError):
            print('error: unreadable or invalid events',file=sys.stderr)
            return 2
    report = assess_answer(answer,events)
    report['answer'] = str(answer_path)
    keys = extract_keys(answer)
    quotes = extract_quotes(answer)
    missing_keys, unread_keys, incomplete_keys = report['keys_missing'],report['keys_unread'],report['keys_incomplete']
    unverified, loops = report['quotes_unverified'],report['tool_loops']
    verification_error, uncited, unfinished = report['verification_error'],report['uncited_answer'],report['unfinished_run']
    problems = report['status'] != 'completed'
    summary = (
        f"# integrity: keys={len(keys)} missing={len(missing_keys)} "
        f"quotes={len(quotes)} unverified={len(unverified)} loops={len(loops)} "
        f"unread={len(unread_keys)} incomplete={len(incomplete_keys)} status={report['status']}"
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
        if unread_keys:
            warnings.append(f"sources not opened: {', '.join(unread_keys)}")
        if incomplete_keys:
            warnings.append(f"sources not fully read: {', '.join(incomplete_keys)}")
        if unverified:
            warnings.append("verbatim quotations not verified against their cited source")
        if verification_error:
            warnings.append(verification_error)
        if uncited:
            warnings.append("answer lacks source evidence or a completed absence protocol")
        if unfinished:
            warnings.append("agent run did not complete")
        prefix = "# WARNING: " + "; ".join(warnings) + "\n\n"
        answer_path.write_text(prefix + answer, encoding="utf-8")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
