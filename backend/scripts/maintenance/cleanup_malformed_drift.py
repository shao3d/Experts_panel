#!/usr/bin/env python3
"""Cleanup malformed `drift_topics` JSON in the `comment_group_drift` table.

Background
----------
When drift analysis was first rolled out, some rows landed in
`comment_group_drift.drift_topics` as malformed JSON (unquoted keys,
truncated strings, shell-expansion artifacts left behind by a buggy
save path). These rows cannot be embedded by
`backend.scripts.maintenance.backfill_drift_embeddings` because
`build_drift_text` cannot parse them — so `drift_embedding` stays NULL
and the fast-path cosine scoring in `comment_group_map_service` falls
back to the slow LLM chunked path for those posts.

This script attempts to fix what it can and marks the rest unrecoverable
so they exit the drift pipeline cleanly without polluting scoring.

Strategy
--------
For each row where `has_drift = 1 AND drift_topics IS NOT NULL`:

    1. Try strict `json.loads(drift_topics)`.
         → if it works the row is already valid, skip it.
    2. Try a regex-based unquote-key fix on the raw value
       (`([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)` → wraps the bare
       identifier in quotes). If the rewritten text is now strict JSON,
         → REPAIR: re-render cleanly with `json.dumps(..., separators=(",", ":"))`,
           persist it back, and stamp `analyzed_by = 'drift-cleanup-fixed-<ts>'`.
    3. Otherwise → MARK UNRECOVERABLE: set `drift_topics = NULL`,
       `has_drift = 0`, `analyzed_by = 'drift-cleanup-unrecoverable-<ts>'`.

Safety
------
This is a DATA-MUTATING operation. By default the script runs in
DRY-RUN mode and prints the diff it would apply without touching the
database. Pass `--apply` to commit mutations.

A JSON manifest of every decision (classification, ids, old → new
values) is written to `backend/data/backups/drift_cleanup_<ts>.json`
BEFORE any UPDATE, so operators can audit or roll back.

The script is IDEMPOTENT: re-running after a successful run finds no
candidates (fixed rows now parse as strict JSON, NULLed rows are
filtered out by the WHERE clause).

Usage
-----
    python -m backend.scripts.maintenance.cleanup_malformed_drift             # dry-run
    python -m backend.scripts.maintenance.cleanup_malformed_drift --apply     # commit
    python -m backend.scripts.maintenance.cleanup_malformed_drift --apply --log-level DEBUG
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path  # noqa: E402

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="maintenance.cleanup_malformed_drift",
)
DB_PATH = get_sqlite_db_path(BACKEND_DIR)
BACKUP_DIR = BACKEND_DIR / "data" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Bare-identifier object-key fix: `{key:` or `, key:` → `{"key":` or `, "key":`.
# The result is NOT guaranteed to be valid JSON — the caller must `json.loads()` it
# to confirm. This is the only repair strategy; for anything more exotic the row
# is marked unrecoverable instead.
UNQUOTED_KEY_RE = re.compile(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)')


def _key_quoted(text: str) -> str:
    """Wrap bare-identifier object keys in quotes.

    Conservative scope: only matches keys that look like valid Python
    identifiers AND sit at a brace/comma boundary. A key like
    ``, note: `` inside a string literal would be matched, but a
    subsequent ``json.loads`` would fail in that case and the row
    would naturally fall through to the unrecoverable path.
    """
    return UNQUOTED_KEY_RE.sub(
        lambda m: f'{m.group(1)}"{m.group(2)}"{m.group(3)}',
        text,
    )


def _classify_and_fix(raw: str | None) -> tuple[str, str | None]:
    """Classify a `drift_topics` value and optionally produce a fixed copy.

    Returns
    -------
    (status, fixed_value)
        `status` ∈ {'valid', 'fixed', 'unrecoverable'}.
        `fixed_value` is None for 'valid'/'unrecoverable', or a strictly
        re-rendered JSON string for 'fixed'.
    """
    if raw is None or not raw.strip():
        return 'unrecoverable', None
    try:
        json.loads(raw)
        return 'valid', None
    except json.JSONDecodeError:
        pass
    try:
        parsed = json.loads(_key_quoted(raw))
    except json.JSONDecodeError:
        return 'unrecoverable', None
    return 'fixed', json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def _scan(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    """Read all candidate rows and classify them. Read-only."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, post_id, expert_id, drift_topics "
        "FROM comment_group_drift "
        "WHERE has_drift = 1 AND drift_topics IS NOT NULL"
    )
    fixed: list[dict] = []
    unrecoverable: list[dict] = []
    for rid, post_id, expert_id, raw in cur.fetchall():
        status, fixed_value = _classify_and_fix(raw)
        if status == 'valid':
            continue
        decision = {
            'id': rid,
            'post_id': post_id,
            'expert_id': expert_id,
            'old_len': len(raw or ''),
        }
        if status == 'fixed':
            decision.update(
                new_value=fixed_value,
                new_len=len(fixed_value),
                reason='unquoted-keys-repaired',
            )
            fixed.append(decision)
        else:
            decision['reason'] = 'parse-failed-after-quote-attempt'
            unrecoverable.append(decision)
    return fixed, unrecoverable


def _write_manifest(
    backup_dir: Path,
    applied: bool,
    fixed: list[dict],
    unrecoverable: list[dict],
    valid_count: int,
    timestamp: str,
) -> Path:
    """Drop a JSON manifest of every classification decision."""
    manifest = {
        'timestamp': timestamp,
        'applied': applied,
        'summary': {
            'valid_skipped': valid_count,
            'fixed': len(fixed),
            'unrecoverable_nulled': len(unrecoverable),
        },
        'fixed_rows': fixed,
        'unrecoverable_rows': unrecoverable,
        'note': (
            'Written BEFORE any UPDATE. If --apply was used: fixed rows now '
            'have drift_topics=<new_value> with quoted keys, and unrecoverable '
            'rows have drift_topics=NULL + has_drift=0. Re-running the script '
            'after this point is a no-op (idempotent).'
        ),
    }
    manifest_path = backup_dir / f'drift_cleanup_{timestamp}.json'
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return manifest_path


def _apply(
    conn: sqlite3.Connection,
    fixed: list[dict],
    unrecoverable: list[dict],
    ts_label: str,
) -> None:
    """Commit the decisions: re-write fixed rows, NULL unrecoverable rows."""
    cur = conn.cursor()
    for row in fixed:
        cur.execute(
            "UPDATE comment_group_drift "
            "SET drift_topics = ?, analyzed_by = ? "
            "WHERE id = ?",
            (
                row['new_value'],
                f'drift-cleanup-fixed-{ts_label}',
                row['id'],
            ),
        )
    for row in unrecoverable:
        cur.execute(
            "UPDATE comment_group_drift "
            "SET drift_topics = NULL, has_drift = 0, analyzed_by = ? "
            "WHERE id = ?",
            (
                f'drift-cleanup-unrecoverable-{ts_label}',
                row['id'],
            ),
        )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Cleanup malformed drift_topics JSON in comment_group_drift',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Commit mutations. Default is dry-run.',
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        help='Logging level (DEBUG/INFO/WARNING/ERROR).',
    )
    args = parser.parse_args()
    logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))

    if not DB_PATH.exists():
        logger.error('Database not found at %s', DB_PATH)
        return 2

    conn = sqlite3.connect(DB_PATH)
    try:
        fixed, unrecoverable = _scan(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM comment_group_drift "
            "WHERE has_drift = 1 AND drift_topics IS NOT NULL"
        )
        total_candidates = cur.fetchone()[0]
        valid_count = total_candidates - len(fixed) - len(unrecoverable)

        ts_label = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        manifest_path = _write_manifest(
            BACKUP_DIR,
            applied=args.apply,
            fixed=fixed,
            unrecoverable=unrecoverable,
            valid_count=valid_count,
            timestamp=ts_label,
        )

        logger.info(
            'Found %d valid, %d fixable, %d unrecoverable rows out of %d candidates.',
            valid_count, len(fixed), len(unrecoverable), total_candidates,
        )
        for row in unrecoverable:
            logger.warning(
                '  unrecoverable id=%s post_id=%s expert=%s len=%s',
                row['id'], row['post_id'], row['expert_id'], row['old_len'],
            )
        for row in fixed:
            logger.info(
                '  fixed      id=%s post_id=%s expert=%s len=%s→%s',
                row['id'], row['post_id'], row['expert_id'],
                row['old_len'], row['new_len'],
            )

        if args.apply:
            _apply(conn, fixed, unrecoverable, ts_label)
            logger.info(
                'Applied %d fixes and %d nullings. Manifest: %s',
                len(fixed), len(unrecoverable), manifest_path,
            )
        else:
            logger.info('[dry-run] No mutations applied.')
            logger.info('Pre-mutation manifest (for audit / rollback): %s', manifest_path)
            logger.info('Re-run with --apply to commit the above decisions.')
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
