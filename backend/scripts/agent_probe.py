#!/usr/bin/env python3
"""Agent-level probe: run the real expert-scout agent on fixture questions and
score the ANSWER (not just retrieval): expected-key recall, hallucinated keys,
abstain honesty, tool-call budget.

Usage:
  backend/.venv/bin/python backend/scripts/agent_probe.py --run --json-out PATH
  backend/.venv/bin/python backend/scripts/agent_probe.py --compare BEFORE.json AFTER.json

Runs scripts/expert_scout.sh per fixture (real LLM runs) — keep the subset small.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
SHIM = REPO_ROOT / "scripts" / "expert_scout.sh"
PROBE_PATH = BACKEND / "scripts" / "search_probe.py"

KEY_RE = re.compile(r"\b([a-z][a-z_]{2,}:\d+)\b")
ABSTAIN_RE = re.compile(r"(нет сигнала|в корпусе нет|не найдено|не покрыто|не содержит|отсутствует|no signal|not covered|not present|gap)", re.IGNORECASE)

AGENT_FIXTURES = [
    "aleph_camera_acidcrunch",
    "grid_prompting",
    "kling_elements_stability",
    "hypermotion_gap",
    "negative_control_out_of_corpus",
]


def _load_probe():
    spec = importlib.util.spec_from_file_location("search_probe_for_agent", PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


def run_agent(question: str, timeout_s: int = 300) -> dict:
    started = time.time()
    proc = subprocess.run(
        ["bash", str(SHIM), question],
        capture_output=True,
        text=True,
        timeout=timeout_s + 60,
    )
    answer = proc.stdout
    meta = {"tool_calls": None, "duration_seconds": round(time.time() - started, 1)}
    for line in proc.stderr.splitlines():
        m = re.search(r"tool_calls=(\d+)", line)
        if m:
            meta["tool_calls"] = int(m.group(1))
        m = re.search(r"artifacts=(\S+)", line)
        if m:
            meta["artifacts"] = m.group(1)
    keys = sorted(set(KEY_RE.findall(answer)))
    keys = [k for k in keys if not k.startswith("localhost:")]
    return {
        "answer_len": len(answer),
        "answer_keys": keys,
        "abstain_signal": bool(ABSTAIN_RE.search(answer.replace("*", "").replace("_", " "))),
        "answer_preview": answer[:400],
        "exit": proc.returncode,
        **meta,
    }


def read_keys_from_events(artifacts: str | None) -> set[str]:
    """source_keys the agent actually opened with `show` (evidence read)."""
    if not artifacts:
        return set()
    events_path = Path(artifacts) / "events.jsonl"
    if not events_path.exists():
        return set()
    read: set[str] = set()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "tool_use":
            continue
        part = event.get("part") or {}
        state = part.get("state") or {}
        args = state.get("input") or part.get("args") or {}
        if part.get("tool") == "scout" and isinstance(args, dict):
            for key in args.get("source_keys") or []:
                read.add(key)
    return read


def score_fixture(fixture: dict, run: dict) -> dict:
    expected = set(fixture["expected_keys"])
    found = set(run["answer_keys"])
    existence = probe.keys_exist(sorted(found)) if found else {}
    hallucinated = sorted(k for k in found if not existence.get(k, False))
    hits = sorted(found & expected)
    recall = (len(hits) / len(expected)) if expected else None
    read = read_keys_from_events(run.get("artifacts"))
    coverage = (len(found & read) / len(read)) if read else None
    abstain_ok = None
    if fixture["kind"] in ("gap", "negative_control"):
        abstain_ok = run["abstain_signal"] and not hallucinated
    return {
        "id": fixture["id"],
        "kind": fixture["kind"],
        "recall": recall,
        "hits": hits,
        "expected_total": len(expected),
        "hallucinated": hallucinated,
        "abstain_ok": abstain_ok,
        "coverage": coverage,
        "read_total": len(read),
        "artifacts": run.get("artifacts"),
        "tool_calls": run.get("tool_calls"),
        "duration_seconds": run.get("duration_seconds"),
    }


def run_all() -> dict:
    fixtures = {f["id"]: f for f in probe.load_fixtures()}
    results = []
    for fid in AGENT_FIXTURES:
        fixture = fixtures[fid]
        print(f"running agent on {fid} ...", file=sys.stderr)
        run = run_agent(fixture["question"])
        scored = score_fixture(fixture, run)
        scored["answer_preview"] = run["answer_preview"]
        results.append(scored)
        print(f"  -> recall={scored['recall']} hallucinated={scored['hallucinated']} abstain_ok={scored['abstain_ok']}", file=sys.stderr)
    hits = [r for r in results if r["kind"] == "hit"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "fixtures": len(results),
            "mean_recall": round(sum(r["recall"] for r in hits if r["recall"] is not None) / max(1, len(hits)), 4),
            "hallucinated_total": sum(len(r["hallucinated"]) for r in results),
            "abstain_ok_total": sum(1 for r in results if r.get("abstain_ok")),
            "abstain_fixtures": sum(1 for r in results if r["kind"] in ("gap", "negative_control")),
        },
        "results": results,
    }


def compare(before_path: str, after_path: str) -> int:
    before = json.loads(Path(before_path).read_text(encoding="utf-8"))
    after = json.loads(Path(after_path).read_text(encoding="utf-8"))
    b = {r["id"]: r for r in before["results"]}
    problems = 0
    for r in after["results"]:
        base = b.get(r["id"])
        if not base:
            continue
        if base.get("recall") is not None and r.get("recall") is not None and r["recall"] < base["recall"] - 1e-9:
            print(f"REGRESSION {r['id']}: recall {base['recall']} -> {r['recall']}")
            problems += 1
        if len(r["hallucinated"]) > len(base["hallucinated"]):
            print(f"REGRESSION {r['id']}: hallucinated {base['hallucinated']} -> {r['hallucinated']}")
            problems += 1
        if base.get("abstain_ok") is True and r.get("abstain_ok") is False:
            print(f"REGRESSION {r['id']}: abstain_ok True -> False")
            problems += 1
        if r["recall"] != base["recall"] or r["hallucinated"] != base["hallucinated"]:
            print(
                f"delta {r['id']}: recall {base['recall']} -> {r['recall']}, "
                f"halluc {len(base['hallucinated'])} -> {len(r['hallucinated'])}, "
                f"abstain {base.get('abstain_ok')} -> {r.get('abstain_ok')}"
            )
    print("summary before:", json.dumps(before["summary"], ensure_ascii=False))
    print("summary after :", json.dumps(after["summary"], ensure_ascii=False))
    print("regressions:", problems)
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    if args.compare:
        return compare(*args.compare)
    if args.run:
        report = run_all()
        print(json.dumps(report["summary"], ensure_ascii=False))
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            print("written:", args.json_out)
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
