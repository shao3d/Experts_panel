#!/usr/bin/env python3
"""Normalize Video Hub timestamp text to the canonical format.

One-time hygiene for rows imported before date normalization landed in
`import_video_json.py`: video segments carry `published_at`/`created_at` in
whatever shape the ingesting agent wrote ("2026-08-07", "2026-08-21T00:00:00",
...). Freshness ranking parses "YYYY-MM-DD HH:MM:SS", so unnormalized rows are
treated as maximally old and the newest videos get ranked last.

Sweeps `expert_id='video_hub'` rows only:
- `posts.created_at` -> canonical text;
- `media_metadata.published_at` -> canonical text (when present);
- `posts_fts.created_at` and `vec_posts.created_at` (both feed Scout freshness;
  the FTS update trigger only fires on message_text changes, so this is
  explicit).

Unparsable values are reported as counts and left untouched — never guess a
date. Prints counts only, never row contents. Production promotion stays behind
the owner's `обнови базу`.

Usage:
    backend/.venv/bin/python backend/scripts/maintenance/normalize_video_timestamps.py --dry-run
    backend/.venv/bin/python backend/scripts/maintenance/normalize_video_timestamps.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path  # noqa: E402
from src.utils.date_utils import format_timestamp, parse_timestamp  # noqa: E402

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="maintenance.normalize_video_timestamps",
)
DEFAULT_DB_PATH = get_sqlite_db_path(BACKEND_DIR)
VIDEO_EXPERT_ID = "video_hub"


def _load_vec_extension(conn: sqlite3.Connection) -> bool:
    """Load sqlite-vec so PRAGMA/UPDATE on the vec_posts virtual table works."""
    try:
        import sqlite_vec  # type: ignore
    except ImportError:
        logger.warning("sqlite_vec package missing; vec_posts left untouched")
        return False
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        logger.warning("sqlite_vec extension unavailable; vec_posts left untouched")
        return False


def _table_exists(cursor: sqlite3.Cursor, name: str) -> bool:
    return (
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            (name,),
        ).fetchone()
        is not None
    )


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    if not _table_exists(cursor, table):
        return False
    return any(
        row[1] == column for row in cursor.execute(f"PRAGMA table_info({table})")
    )


def normalize_video_timestamps(db_path: Path, *, dry_run: bool = False) -> dict:
    counts = {
        "scanned": 0,
        "updated_posts": 0,
        "updated_meta_published": 0,
        "updated_fts": 0,
        "updated_vec": 0,
        "already_canonical": 0,
        "unparsable": 0,
        "vec_verify_failed": 0,
    }

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    vec_ok = _load_vec_extension(conn)
    try:
        rows = cursor.execute(
            "SELECT post_id, created_at, media_metadata FROM posts WHERE expert_id = ?",
            (VIDEO_EXPERT_ID,),
        ).fetchall()

        for post_id, created_at, media_raw in rows:
            counts["scanned"] += 1
            parsed = parse_timestamp(created_at)
            if parsed is None:
                counts["unparsable"] += 1
                logger.warning(
                    "unparsable created_at for video post_id=%s; left untouched",
                    post_id,
                )
                continue
            canonical = format_timestamp(parsed)

            new_meta = media_raw
            meta_obj = None
            if media_raw:
                try:
                    meta_obj = json.loads(media_raw)
                except (ValueError, TypeError):
                    meta_obj = None
            if isinstance(meta_obj, dict):
                raw_published = meta_obj.get("published_at")
                parsed_published = (
                    parse_timestamp(raw_published)
                    if raw_published not in (None, "")
                    else None
                )
                canonical_published = (
                    format_timestamp(parsed_published)
                    if parsed_published is not None
                    else None
                )
                if canonical_published and canonical_published != raw_published:
                    meta_obj["published_at"] = canonical_published
                    new_meta = json.dumps(meta_obj, ensure_ascii=False)
                    counts["updated_meta_published"] += 1

            if canonical == created_at and new_meta == media_raw:
                counts["already_canonical"] += 1
                continue

            if not dry_run:
                cursor.execute(
                    "UPDATE posts SET created_at = ?, media_metadata = ? WHERE post_id = ?",
                    (canonical, new_meta, post_id),
                )
            counts["updated_posts"] += 1

            if _column_exists(cursor, "posts_fts", "created_at"):
                if not dry_run:
                    cursor.execute(
                        "UPDATE posts_fts SET created_at = ? WHERE rowid = ?",
                        (canonical, post_id),
                    )
                counts["updated_fts"] += 1

            if vec_ok and _column_exists(cursor, "vec_posts", "created_at"):
                if not dry_run:
                    cursor.execute(
                        "UPDATE vec_posts SET created_at = ? WHERE post_id = ?",
                        (canonical, post_id),
                    )
                    stored = cursor.execute(
                        "SELECT created_at FROM vec_posts WHERE post_id = ?",
                        (post_id,),
                    ).fetchone()
                    if stored and stored[0] != canonical:
                        counts["vec_verify_failed"] += 1
                        logger.warning(
                            "vec_posts.created_at not applied for post_id=%s "
                            "(sqlite-vec UPDATE no-op?); re-run embed_posts for it",
                            post_id,
                        )
                        continue
                counts["updated_vec"] += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database (default: staging dev DB)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).expanduser().resolve()
    if not db_path.exists():
        logger.error("database not found: %s", db_path)
        return 1
    counts = normalize_video_timestamps(db_path, dry_run=args.dry_run)
    prefix = "DRY RUN: would update" if args.dry_run else "updated"
    logger.info(
        "%s %d/%d video rows (meta published_at: %d, fts: %d, vec: %d; "
        "already canonical: %d, unparsable: %d, vec verify failed: %d)",
        prefix,
        counts["updated_posts"],
        counts["scanned"],
        counts["updated_meta_published"],
        counts["updated_fts"],
        counts["updated_vec"],
        counts["already_canonical"],
        counts["unparsable"],
        counts["vec_verify_failed"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
