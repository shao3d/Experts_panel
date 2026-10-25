#!/usr/bin/env python3
"""Normalize VideoHub author labels in the staging DB (staging only).

The same YouTube channel can be imported under different author labels
(``JOEY`` vs ``JOEY (noisygroup)``), which splits the corpus catalog and the
generated index into two sections.  This script rewrites only the two author
fields inside ``posts.media_metadata`` for ``expert_id='video_hub'`` and leaves
segments, text, timestamps and receipts untouched.

Usage:
  backend/.venv/bin/python backend/scripts/normalize_video_authors.py --dry-run
  backend/.venv/bin/python backend/scripts/normalize_video_authors.py --apply

The mapping lives in ``backend/src/utils/video_authors.py`` and is the same one
the importer uses, so the repair and future ingests cannot drift apart.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

sys.path.insert(0, str(BACKEND_DIR))
from src.utils.video_authors import canonical_author_by_id  # noqa: E402

DEFAULT_DB = REPO_ROOT / "backend" / "data" / "experts.db"
EXPERT_ID = "video_hub"


def collect(conn: sqlite3.Connection) -> tuple[list[tuple[int, dict, str, str]], Counter]:
    """Return rows to rewrite plus a per-video summary."""
    rows: list[tuple[int, dict, str, str]] = []
    by_video: Counter = Counter()
    for post_id, meta_raw in conn.execute(
        "SELECT post_id, media_metadata FROM posts WHERE expert_id = ? AND media_metadata IS NOT NULL",
        (EXPERT_ID,),
    ):
        try:
            meta = json.loads(meta_raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(meta, dict) or meta.get("type") != "video_segment":
            continue
        target = canonical_author_by_id(meta.get("original_author_id"))
        if not target:
            continue
        name, author_id = target
        if meta.get("original_author") == name and meta.get("original_author_id") == author_id:
            continue
        rows.append((post_id, meta, name, author_id))
        by_video[(meta.get("video_url", "?"), meta.get("video_title", ""))] += 1
    return rows, by_video


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true", help="report only (default when --apply is absent)")
    parser.add_argument("--apply", action="store_true", help="write changes in one transaction")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        rows, by_video = collect(conn)
        print(f"rows to rewrite: {len(rows)} in {len(by_video)} video(s)")
        for (url, title), count in sorted(by_video.items(), key=lambda item: -item[1]):
            print(f"  {count:4d} seg  {url}  {title[:70]}")
        if not rows:
            print("nothing to do")
            return 0
        if not args.apply:
            print("\ndry-run: no changes written (pass --apply to write)")
            return 0

        with conn:
            for post_id, meta, name, author_id in rows:
                meta["original_author"] = name
                meta["original_author_id"] = author_id
                conn.execute(
                    "UPDATE posts SET media_metadata = ? WHERE post_id = ?",
                    (json.dumps(meta, ensure_ascii=False), post_id),
                )
        print(f"\napplied: {len(rows)} row(s) updated")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
