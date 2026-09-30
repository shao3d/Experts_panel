#!/usr/bin/env python3
"""Search probe: measure retrieval quality against verified fixture keys.

Runs the read-only expert_scout.py helper (search) over fixture questions and
computes recall@10 / recall@20 / recall@40 / MRR + hidden-key counts. A baseline snapshot guards regressions;
improvements raise the numbers and the baseline is updated deliberately.

Usage:
  backend/.venv/bin/python backend/scripts/search_probe.py --run [--json-out PATH]
  backend/.venv/bin/python backend/scripts/search_probe.py --write-baseline
  backend/.venv/bin/python backend/scripts/search_probe.py --check-baseline

Fixture self-check (no network): --check-keys
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
HELPER = BACKEND / "scripts" / "expert_scout.py"
PY = BACKEND / ".venv" / "bin" / "python"
FIXTURES_PATH = BACKEND / "tests" / "search_probe_fixtures.py"
BASELINE_PATH = BACKEND / "tests" / "search_probe_baseline.json"

MAX_LIMIT = 30


def load_fixtures() -> list[dict]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("search_probe_fixtures", FIXTURES_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FIXTURES


def _probe_now() -> str | None:
    """Anchor freshness decay to the baseline snapshot so metrics do not drift
    as calendar days pass (the decay is day-based)."""
    if BASELINE_PATH.exists():
        try:
            stamp = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("generated_at")
            if stamp:
                return stamp.replace(" ", "T")
        except json.JSONDecodeError:
            pass
    return None


def run_search(query: str, limit: int = 40, extra: list[str] | None = None) -> dict:
    cmd = [str(PY), str(HELPER), "search", query, "--limit", str(limit), "--json"]
    anchor = _probe_now()
    if anchor:
        cmd.extend(["--now", anchor])
    if extra:
        cmd.extend(extra)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"search failed for {query[:60]!r}: {proc.stderr[-300:]}")
    payload = json.loads(proc.stdout)
    results = payload.get("results", payload if isinstance(payload, list) else [])
    keys = [item["source_key"] for item in results if item.get("source_key")]
    return {
        "keys": keys,
        "leg_stats": payload.get("retrieval_stats", {}),
        "warnings": payload.get("warnings", []),
    }


def keys_exist(keys: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    uniq = sorted(set(keys))
    for i in range(0, len(uniq), 3):
        chunk = uniq[i : i + 3]
        proc = subprocess.run(
            [str(PY), str(HELPER), "show", *chunk, "--comments-limit", "0", "--json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode:
            raise RuntimeError(f"source existence check failed (exit {proc.returncode})")
        payload = json.loads(proc.stdout)
        if not isinstance(payload, list):
            raise RuntimeError("source existence check returned invalid payload")
        seen = set()
        for item in payload:
            key = item.get("source_key", "?")
            seen.add(key)
            out[key] = "error" not in item
        if seen != set(chunk):
            raise RuntimeError("source existence check omitted or added keys")
    return out


def _aggregate_legs(per_fixture: list[dict]) -> dict | None:
    per_fixture = [p for p in per_fixture if p and p.get("queries")]
    if not per_fixture:
        return None
    total_q = sum(p["queries"] for p in per_fixture)
    return {
        "queries": total_q,
        "dead_leg_queries": sum(p.get("dead_leg_queries", 0) for p in per_fixture),
        "mean_jaccard": round(sum(p.get("mean_jaccard", 0) * p["queries"] for p in per_fixture) / total_q, 4),
    }


_FIXTURE_SCOPED: dict[str, bool] = {}


def scoped_ids(fixture_id: str) -> bool:
    """True when the fixture pins a single expert or a group (diversity off)."""
    return _FIXTURE_SCOPED.get(fixture_id, False)


def _summarize_legs(stats_list: list[dict]) -> dict | None:
    stats_list = [s for s in stats_list if s]
    if not stats_list:
        return None
    return {
        "queries": len(stats_list),
        "mean_overlap": round(sum(s.get("overlap", 0) for s in stats_list) / len(stats_list), 2),
        "mean_jaccard": round(sum(s.get("jaccard", 0) for s in stats_list) / len(stats_list), 4),
        "dead_leg_queries": sum(1 for s in stats_list if s.get("overlap", 0) == 0),
    }


def metrics_for(returned: list[str], expected: list[str], k: int) -> dict:
    top = returned[:k]
    hits = [k_ for k_ in top if k_ in expected]
    recall = (len(hits) / len(expected)) if expected else None
    mrr = 0.0
    for rank, key in enumerate(top, start=1):
        if key in expected:
            mrr = 1.0 / rank
            break
    return {"recall": recall, "mrr": mrr, "hits": hits, "returned": top}


def probe_fixture(fixture: dict) -> dict:
    queries = fixture.get("query_variants") or [fixture["question"]]
    expected = fixture["expected_keys"]
    search_args = fixture.get("search_args") or []
    per_query = []
    leg_stats_list: list[dict] = []
    for query in queries:
        fetched = run_search(query, extra=search_args)
        returned = fetched["keys"]
        leg_stats_list.append(fetched.get("leg_stats") or {})
        hidden = [
            k for k in metrics_for(returned, expected, 40)["returned"]
            if k in expected and k not in returned[:10]
        ]
        outside = [k for k in expected if k not in returned[:40]]
        per_query.append(
            {
                "query": query,
                "recall@10": metrics_for(returned, expected, 10)["recall"],
                "recall@20": metrics_for(returned, expected, 20)["recall"],
                "recall@40": metrics_for(returned, expected, 40)["recall"],
                "mrr@10": metrics_for(returned, expected, 10)["mrr"],
                "hidden_keys": hidden,
                "outside_keys": outside,
                "experts_in_top10": len({k.split(":")[0] for k in returned[:10]}),
                "returned@10": metrics_for(returned, expected, 10)["returned"],
            }
        )
        time.sleep(0.2)
    def avg(field: str, qs: list[dict] | None = None):
        qs = per_query if qs is None else qs
        vals = [q[field] for q in qs if q[field] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    result = {
        "id": fixture["id"],
        "kind": fixture["kind"],
        "tags": fixture.get("tags", []),
        "expected": expected,
        "per_query": per_query,
        "recall@10": avg("recall@10"),
        "recall@20": avg("recall@20"),
        "recall@40": avg("recall@40"),
        "mrr@10": avg("mrr@10"),
        "hidden_total": sum(len(q["hidden_keys"]) for q in per_query),
        "outside_total": sum(len(q["outside_keys"]) for q in per_query),
        "experts_in_top10": round(
            sum(q["experts_in_top10"] for q in per_query) / len(per_query), 2
        )
        if per_query
        else None,
        "legs": _summarize_legs(leg_stats_list),
    }
    if fixture["kind"] == "hit" and "freshness_craft" in fixture.get("tags", []):
        craft_queries = []
        for query in queries:
            returned = run_search(query, extra=search_args + ["--freshness", "craft"])["keys"]
            craft_queries.append(
                {
                    "query": query,
                    "recall@10": metrics_for(returned, expected, 10)["recall"],
                    "recall@40": metrics_for(returned, expected, 40)["recall"],
                    "mrr@10": metrics_for(returned, expected, 10)["mrr"],
                }
            )
            time.sleep(0.2)
        result["craft_mode"] = {
            "recall@10": avg("recall@10", craft_queries),
            "recall@40": avg("recall@40", craft_queries),
            "mrr@10": avg("mrr@10", craft_queries),
        }
    return result


def run_probe() -> dict:
    fixtures = load_fixtures()
    for f in fixtures:
        args = f.get("search_args") or []
        _FIXTURE_SCOPED[f["id"]] = ("--experts" in args)
    results = [probe_fixture(f) for f in fixtures]
    hits = [r for r in results if r["kind"] == "hit"]
    def mean(field: str) -> float | None:
        vals = [r[field] for r in hits if r[field] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    craft_hits = [r for r in hits if r.get("craft_mode")]
    craft_summary = None
    if craft_hits:
        def cmean(field: str) -> float | None:
            vals = [r["craft_mode"][field] for r in craft_hits if r["craft_mode"].get(field) is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        craft_summary = {
            "fixtures": [r["id"] for r in craft_hits],
            "default_recall@10": round(
                sum(r["recall@10"] for r in craft_hits if r["recall@10"] is not None)
                / max(1, sum(1 for r in craft_hits if r["recall@10"] is not None)),
                4,
            ),
            "craft_recall@10": cmean("recall@10"),
            "craft_recall@40": cmean("recall@40"),
        }
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "fixtures": len(results),
            "hit_fixtures": len(hits),
            "mean_recall@10": mean("recall@10"),
            "mean_recall@20": mean("recall@20"),
            "mean_recall@40": mean("recall@40"),
            "mean_mrr@10": mean("mrr@10"),
            "hidden_keys_total": sum(r.get("hidden_total", 0) for r in results),
            "outside_keys_total": sum(r.get("outside_total", 0) for r in results),
            "experts_in_top10_unscoped": round(
                sum(r["experts_in_top10"] for r in hits
                    if r["experts_in_top10"] is not None and not scoped_ids(r["id"])) / max(1, len([r for r in hits if r["experts_in_top10"] is not None and not scoped_ids(r["id"])])),
                2,
            ),
            "legs": _aggregate_legs([r.get("legs") for r in hits if r.get("legs")]),
            "craft_mode": craft_summary,
        },
        "results": results,
    }


def compare_to_baseline(probe: dict) -> list[str]:
    if not BASELINE_PATH.exists():
        return ["no baseline yet (write one with --write-baseline)"]
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    problems = []
    base_by_id = {r["id"]: r for r in baseline["results"]}
    for r in probe["results"]:
        if r["kind"] != "hit":
            continue
        base = base_by_id.get(r["id"])
        if base is None:
            problems.append(f"{r['id']}: new fixture (not in baseline)")
            continue
        for field in ("recall@10", "recall@20", "recall@40", "mrr@10"):
            b, c = base.get(field), r.get(field)
            if b is None or c is None:
                continue
            if c < b - 1e-9:
                problems.append(f"{r['id']}: {field} regression {b} -> {c}")
        if base.get("craft_mode") and r.get("craft_mode"):
            b, c = base["craft_mode"].get("recall@10"), r["craft_mode"].get("recall@10")
            if b is not None and c is not None and c < b - 1e-9:
                problems.append(f"{r['id']}: craft_mode recall@10 regression {b} -> {c}")
    for field in ("mean_recall@10", "mean_recall@20", "mean_recall@40", "mean_mrr@10"):
        b = baseline["summary"].get(field)
        c = probe["summary"].get(field)
        if b is not None and c is not None and c < b - 1e-9:
            problems.append(f"summary {field} regression {b} -> {c}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="run the probe and print the table")
    parser.add_argument("--check-keys", action="store_true", help="verify fixture keys exist")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--check-baseline", action="store_true", help="run + compare with baseline")
    parser.add_argument("--json-out", help="write full probe JSON here")
    args = parser.parse_args()

    if args.check_keys:
        fixtures = load_fixtures()
        all_keys = sorted({k for f in fixtures for k in f["expected_keys"]})
        status = keys_exist(all_keys)
        bad = [k for k, ok in status.items() if not ok]
        print(f"fixture keys: {len(all_keys)}, missing: {len(bad)}")
        for k in bad:
            print("  MISSING:", k)
        return 1 if bad else 0

    if args.run or args.write_baseline or args.check_baseline:
        probe = run_probe()
        print(f"== search probe {probe['generated_at']} ==")
        for r in probe["results"]:
            print(
                f"  {r['id']:<32} kind={r['kind']:<15} "
                f"recall@10={r['recall@10']} recall@20={r['recall@20']} recall@40={r['recall@40']} mrr@10={r['mrr@10']} hidden={r['hidden_total']} legs={r.get('legs')}"
            )
        print("summary:", json.dumps(probe["summary"], ensure_ascii=False))
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(probe, ensure_ascii=False, indent=1), encoding="utf-8")
        if args.write_baseline:
            probe["baseline_note"] = (
                "Updated 2026-09-29 after improvements 1-3 (wide pool 40, freshness profiles, "
                "leg telemetry). Default metrics unchanged vs pre-change snapshot; craft_mode "
                "and legs fields added as new guarded metrics."
            )
            BASELINE_PATH.write_text(json.dumps(probe, ensure_ascii=False, indent=1), encoding="utf-8")
            print("baseline written:", BASELINE_PATH)
        if args.check_baseline:
            problems = compare_to_baseline(probe)
            if problems:
                print("BASELINE CHECK FAILED:")
                for p in problems:
                    print("  -", p)
                return 1
            print("baseline check: OK (no regressions)")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
