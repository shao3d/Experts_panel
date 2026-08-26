#!/usr/bin/env python3
"""Janitor for the headless opencode serve (:4096) on the VM.

Two problems this solves (observed 2026-08-26):
  1. Finished drift/synthesis sessions accumulate forever (~100 drift_* found).
  2. Sessions stuck in a server-side retry loop (e.g. provider monthly quota
     exhausted) hold model slots indefinitely until manually aborted.

Stdlib-only (urllib), so it runs on the host without the backend venv.

Usage:
  opencode_serve_janitor.py            # dry-run: print what would happen
  opencode_serve_janitor.py --apply    # actually abort/delete
Options:
  --max-age-hours N    delete known-prefix sessions idle longer than N (6)
  --purge-all-stale    also delete ANY session idle longer than max-age
                       (not just known prefixes; use with care)
"""

import argparse
import json
import sys
import time
import urllib.request

OPENCODE_URL = "http://127.0.0.1:4096"
# Machine-generated task-session title prefixes (drift client, reddit synth
# client, live-navigator ingestion agents). Human/manual sessions are spared
# unless --purge-all-stale is passed.
KNOWN_PREFIXES = (
    "drift_", "driftb_", "reddit_synth_",
    "trans_", "synth_", "synthcl_", "class_", "parse_",
)


def _api(path: str, method: str = "GET", timeout: int = 8):
    req = urllib.request.Request(f"{OPENCODE_URL}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, body
    except Exception as e:
        return None, str(e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually abort/delete (default: dry-run)")
    ap.add_argument("--max-age-hours", type=float, default=6.0)
    ap.add_argument("--purge-all-stale", action="store_true",
                    help="also delete unknown-prefix stale sessions")
    args = ap.parse_args()

    now_ms = time.time() * 1000
    cutoff = now_ms - args.max_age_hours * 3600 * 1000
    aborted = deleted = errors = 0

    status, body = _api("/session/status")
    if status is None:
        print(f"opencode serve unreachable: {body}")
        return 1
    if body.strip().startswith("{") and body.strip() != "{}":
        for sid, info in json.loads(body).items():
            updated = info.get("time", {}).get("updated") or now_ms
            if updated <= cutoff:
                print(f"[stuck-retry] {sid}: {str(info.get('message'))[:80]}")
                if args.apply:
                    s, _ = _api(f"/session/{sid}/abort", "POST")
                    errors += s is None
                aborted += 1

    status, body = _api("/session?limit=1000")
    if status is None:
        print(f"opencode serve unreachable: {body}")
        return 1
    for sess in json.loads(body):
        title = sess.get("title") or ""
        sid = sess.get("id")
        updated = (sess.get("time") or {}).get("updated") or \
                  (sess.get("time") or {}).get("created") or now_ms
        if updated > cutoff:
            continue
        known = title.startswith(KNOWN_PREFIXES)
        age_h = (now_ms - updated) / 3600000
        if not (known or args.purge_all_stale):
            continue
        print(f"[stale] {sid} '{title}' idle {age_h:.1f}h -> delete")
        if args.apply:
            _api(f"/session/{sid}/abort", "POST")
            s, err = _api(f"/session/{sid}", "DELETE")
            if s is None:
                errors += 1
                print(f"  delete failed: {err}")
        deleted += 1

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"{mode}: would-abort={aborted} would-delete={deleted} errors={errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
