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
ABSTAIN_RE = re.compile(r"(нет сигнала|в корпусе нет|не наш[её]л|не найдено|не удалось найти|не покрыто|не содержит|отсутствует|no signal|not found|not covered|not present|gap)", re.IGNORECASE)

AGENT_FIXTURES = [
    "aleph_camera_acidcrunch",
    "grid_prompting",
    "kling_elements_stability",
    "hypermotion_gap",
    "minimax_degradation",
    "videohub_liquid_speed_ramp",
    "videohub_dialogue_language",
    "videohub_character_sheet_model",
    "videohub_fake_fall",
    "negative_control_out_of_corpus",
    "videohub_liquid_plain_language",
    "videohub_character_sheet_false_premise",
]


def _load_probe():
    spec = importlib.util.spec_from_file_location("search_probe_for_agent", PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()


def run_agent(question: str, timeout_s: int = 900, engine: str = "runtime") -> dict:
    # Reuse the live-stream evaluator. Saved operational logs are not an
    # evaluation input, and a requested show is never counted as a read.
    spec = importlib.util.spec_from_file_location('scout_benchmark_for_probe', BACKEND/'scripts/benchmark_scout_models.py')
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    result = benchmark.run(engine,'agent_probe',timeout_s,question=question)
    answer = result['answer']
    opened = set(result['cited_keys']) - set(result['citations_without_captured_show']) - set(result['citations_incompletely_read'])
    keys = sorted(set(KEY_RE.findall(answer)))
    keys = [k for k in keys if not k.startswith("localhost:")]
    return {
        "answer": answer,
        "answer_len": len(answer),
        "answer_keys": keys,
        "abstain_signal": bool(ABSTAIN_RE.search(answer[:600].replace("*", "").replace("_", " "))),
        "answer_preview": answer[:400],
        "diagnostics": result.get("diagnostics", []),
        "exit": result['exit'],
        "run_completed": result['run_completed'],
        "integrity": result['integrity'],
        "read_keys": sorted(opened),
        "read_total": result['fully_read_sources'],
        "tool_calls": result['tool_calls'],
        "duration_seconds": result['duration_seconds'],
    }


def score_fixture(fixture: dict, run: dict) -> dict:
    expected = set(fixture["expected_keys"])
    found = set(run["answer_keys"])
    existence = probe.keys_exist(sorted(found)) if found else {}
    hallucinated = sorted(k for k in found if not existence.get(k, False))
    hits = sorted(found & expected)
    recall = (len(hits) / len(expected)) if expected else None
    read = set(run.get('read_keys', []))
    coverage = (len(found & read) / run.get('read_total',len(read))) if run.get('read_total',len(read)) else None
    succeeded = run.get('exit') == 0 and run.get('run_completed',False) and run.get('integrity',{}).get('status')=='completed'
    abstain_ok = None
    if fixture["kind"] in ("gap", "negative_control"):
        abstain_ok = succeeded and run["abstain_signal"] and not hallucinated and not (found-read)
        if not fixture.get("allow_context_citations", False):
            abstain_ok = abstain_ok and not found
    # Expected keys are accepted alternatives, not a demand to cite all of them.
    missing_groups = [name for name, keys in fixture.get("required_groups", {}).items()
                      if not (found & read & set(keys))]
    reasons = []
    if not succeeded:
        reasons.append("run_failed")
    if hallucinated:
        reasons.append("nonexistent_sources")
    if found-read:
        reasons.append("unread_sources")
    if fixture["kind"] == "hit":
        if len(found & read & expected) < fixture.get("min_hits", 1):
            reasons.append("insufficient_expected_sources")
        if missing_groups:
            reasons.append("missing_facets")
        if fixture.get("max_sources") is not None and len(found) > fixture["max_sources"]:
            reasons.append("too_many_sources")
    elif not abstain_ok:
        reasons.append("abstention_failed")
    return {
        "id": fixture["id"],
        "fixture_signature": probe.fixture_signature(fixture),
        "automatic_pass": not reasons,
        "failure_reasons": reasons,
        "missing_groups": missing_groups,
        "unjudged_keys": sorted(found-expected),
        "kind": fixture["kind"],
        "recall": recall,
        "hits": hits,
        "expected_total": len(expected),
        "hallucinated": hallucinated,
        "abstain_ok": abstain_ok,
        "coverage": coverage,
        "read_total": run.get('read_total',len(read)),
        "unopened_citations": sorted(found-read),
        "evidence_precision": len(found & read)/len(found) if found else None,
        "run_succeeded": succeeded,
        "exit": run.get('exit'),
        "integrity": run.get('integrity'),
        "diagnostics": run.get("diagnostics", []),
        "tool_calls": run.get("tool_calls"),
        "duration_seconds": run.get("duration_seconds"),
    }


def run_all(timeout_s: int = 900, fixture_ids: list[str] | None = None, show_answers: bool = False, engine: str = "runtime") -> dict:
    fixtures = {f["id"]: f for f in probe.load_fixtures()}
    results = []
    for fid in fixture_ids or AGENT_FIXTURES:
        fixture = fixtures[fid]
        if not fixture.get("reviewed_at"):
            raise ValueError(f"{fid}: source review required before agent acceptance")
        print(f"running agent on {fid} ...", file=sys.stderr)
        run = run_agent(fixture["question"], timeout_s, engine)
        scored = score_fixture(fixture, run)
        scored["answer_preview"] = run["answer_preview"]
        if show_answers:
            print(f"ANSWER {fid}:\n{run['answer']}\n", flush=True)
        results.append(scored)
        if not scored["run_succeeded"]:
            print("Run diagnostics: " + json.dumps(run.get("diagnostics", []), ensure_ascii=False), file=sys.stderr)
        print(f"  -> pass={scored['automatic_pass']} reasons={scored['failure_reasons']} recall={scored['recall']} hallucinated={scored['hallucinated']} abstain_ok={scored['abstain_ok']}", file=sys.stderr)
    hits = [r for r in results if r["kind"] == "hit"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engine": engine,
        "summary": {
            "fixtures": len(results),
            "mean_recall": round(sum(r["recall"] for r in hits if r["recall"] is not None) / max(1, len(hits)), 4),
            "hallucinated_total": sum(len(r["hallucinated"]) for r in results),
            "failed_runs": sum(not r['run_succeeded'] for r in results),
            "automatic_passes": sum(r["automatic_pass"] for r in results),
            "quality_failures": sum(not r["automatic_pass"] for r in results),
            "abstain_ok_total": sum(1 for r in results if r.get("abstain_ok")),
            "abstain_fixtures": sum(1 for r in results if r["kind"] in ("gap", "negative_control")),
        },
        "results": results,
    }


def compare(before_path: str, after_path: str) -> int:
    before = json.loads(Path(before_path).read_text(encoding="utf-8"))
    after = json.loads(Path(after_path).read_text(encoding="utf-8"))
    b = {r["id"]: r for r in before["results"]}
    missing = set(b) - {r['id'] for r in after['results']}
    problems = len(missing)
    for fid in sorted(missing):
        print(f'REGRESSION {fid}: result missing')
    for r in after["results"]:
        base = b.get(r["id"])
        if not base:
            continue
        if base.get('run_succeeded',True) and not r.get('run_succeeded',True):
            print(f"REGRESSION {r['id']}: failed run")
            problems += 1
        if base.get("fixture_signature") != r.get("fixture_signature"):
            print(f"INCOMPARABLE {r['id']}: fixture contract changed")
            problems += 1
            continue
        if base.get("automatic_pass") and not r.get("automatic_pass"):
            print(f"REGRESSION {r['id']}: answer acceptance failed")
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
    parser.add_argument("--fixtures", nargs="+", choices=[f["id"] for f in probe.load_fixtures()])
    parser.add_argument("--engine", choices=["runtime", "sol", "luna", "bunny", "mimo"], default="runtime")
    parser.add_argument("--show-answers", action="store_true", help="Print live answers for semantic review")
    parser.add_argument('--timeout',type=int,default=900)
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    if args.compare:
        return compare(*args.compare)
    if args.run:
        report = run_all(args.timeout, args.fixtures, args.show_answers, args.engine)
        print(json.dumps(report["summary"], ensure_ascii=False))
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            print("written:", args.json_out)
        return 1 if report['summary']['quality_failures'] else 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
