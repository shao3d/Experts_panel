#!/usr/bin/env python3
"""A/B: drift analysis via headless opencode vs stored Gemini verdicts.

Read-only against the DB: never touches statuses or results.
Usage:
    .venv/bin/python scripts/ab_test_drift_opencode.py [--n 50] [--concurrency 3]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from src.services.opencode_drift_client import analyze, check_serve_health  # noqa: E402


def load_sample(n: int, filter_mode: str = "drift") -> list[dict]:
    import sqlite3
    db = os.getenv("DATABASE_URL", "sqlite:///data/experts.db").replace("sqlite:///", "")
    if not os.path.isabs(db):
        db = os.path.join(BACKEND_DIR, db)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    if filter_mode == "drift":
        cond = "cgd.analyzed_by = 'drift_checked_gemini' AND cgd.drift_topics IS NOT NULL"
    elif filter_mode == "nodrift":
        cond = "cgd.analyzed_by = 'drift_checked_gemini' AND cgd.has_drift = 0"
    else:
        raise SystemExit("filter: drift|nodrift")
    rows = con.execute(f"""
        SELECT cgd.post_id, cgd.has_drift, cgd.drift_topics, p.message_text
        FROM comment_group_drift cgd JOIN posts p ON p.post_id = cgd.post_id
        WHERE {cond}
        ORDER BY RANDOM()
        LIMIT :n
    """, {"n": n}).fetchall()

    sample = []
    for pid, has_drift, topics, post_text in rows:
        comments = [
            {"author": a, "text": t}
            for a, t in con.execute(
                "SELECT author_name, comment_text FROM comments "
                "WHERE post_id=? ORDER BY comment_id LIMIT 8", (pid,))
        ]
        sample.append({
            "post_id": pid,
            "gemini_has_drift": bool(has_drift),
            "gemini_topics": json.loads(topics) if isinstance(topics, str) else (topics or {}),
            "post_text": post_text or "",
            "comments": comments,
        })
    con.close()
    return sample


def norm_tokens(items) -> set:
    toks = set()
    for it in items or []:
        for w in str(it).lower().split():
            tok = "".join(ch for ch in w if ch.isalnum())
            if len(tok) > 2:
                toks.add(tok)
    return toks


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def compare_one(group: dict) -> dict:
    t0 = time.time()
    rec = {
        "post_id": group["post_id"],
        "gemini_has_drift": group["gemini_has_drift"],
        "ok": False,
        "error": None,
        "latency_s": None,
        "agreement": None,
        "keyword_jaccard": None,
    }
    try:
        result = analyze(group["post_text"], group["comments"])
        rec["ok"] = True
        rec["latency_s"] = round(time.time() - t0, 1)
        new_drift = bool(result.get("has_drift"))
        rec["opencode_has_drift"] = new_drift
        rec["confidence"] = result.get("confidence")
        rec["agreement"] = new_drift == group["gemini_has_drift"]

        def all_keywords(topics_obj):
            out = []
            if isinstance(topics_obj, dict):
                for t in topics_obj.get("drift_topics") or []:
                    out.extend(t.get("keywords") or [])
            elif isinstance(topics_obj, list):
                for t in topics_obj:
                    out.extend(t.get("keywords") or [])
            return out

        g_kw = norm_tokens(all_keywords(
            group["gemini_topics"] if isinstance(group["gemini_topics"], dict)
            else group["gemini_topics"]))
        o_kw = norm_tokens(all_keywords(result))
        if g_kw or o_kw:
            rec["keyword_jaccard"] = round(jaccard(g_kw, o_kw), 3)
    except Exception as e:
        rec["error"] = str(e)[:200]
        rec["latency_s"] = round(time.time() - t0, 1)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--filter", choices=["drift","nodrift"], default="drift")
    ap.add_argument("--concurrency", type=int,
                    default=int(os.getenv("DRIFT_CONCURRENCY", "3")))
    args = ap.parse_args()

    if not check_serve_health():
        print("❌ opencode serve недоступен на", os.getenv(
            "OPENCODE_URL", "http://127.0.0.1:4096"))
        sys.exit(1)

    sample = load_sample(args.n, args.filter)
    print(f"A/B выборка: {len(sample)} групп, concurrency={args.concurrency}")
    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(compare_one, g): g["post_id"] for g in sample}
        for fut in as_completed(futures):
            rec = fut.result()
            results.append(rec)
            done += 1
            mark = "OK " if rec["ok"] else "ERR"
            agree = "" if rec.get("agreement") is None else (
                "agree" if rec["agreement"] else "DISAGREE")
            print(f"  [{done}/{len(sample)}] {mark} post={futures[fut]} "
                  f"{rec['latency_s']}s {agree} "
                  f"jac={rec.get('keyword_jaccard')} {('err=' + rec['error'][:60]) if rec['error'] else ''}")

    ok = [r for r in results if r["ok"]]
    errs = [r for r in results if not r["ok"]]
    agreed = [r for r in ok if r["agreement"]]
    both_drift = [r for r in ok if r["agreement"] and r["gemini_has_drift"]]
    jacs = [r["keyword_jaccard"] for r in both_drift if r["keyword_jaccard"] is not None]
    lats = sorted(r["latency_s"] for r in ok)

    report = {
        "n": len(results),
        "json_ok": len(ok),
        "json_failed": len(errs),
        "has_drift_agreement_pct": round(100 * len(agreed) / len(ok), 1) if ok else None,
        "mean_keyword_jaccard_both_drift": round(sum(jacs) / len(jacs), 3) if jacs else None,
        "latency_avg_s": round(sum(lats) / len(lats), 1) if lats else None,
        "latency_p90_s": lats[int(0.9 * len(lats)) - 1] if lats else None,
        "results": results,
    }

    out_dir = BACKEND_DIR / "data" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ab_drift_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n══════════ ИТОГИ A/B ══════════")
    print(f"Валидный JSON : {len(ok)}/{len(results)}")
    print(f"Согласие has_drift: {report['has_drift_agreement_pct']}%")
    print(f"Keyword Jaccard (оба видят дрифт): {report['mean_keyword_jaccard_both_drift']}")
    print(f"Латентность: avg {report['latency_avg_s']}s / p90 {report['latency_p90_s']}s")
    print(f"Отчёт: {out_path}")


if __name__ == "__main__":
    main()
