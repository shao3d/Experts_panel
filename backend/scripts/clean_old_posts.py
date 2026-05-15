#!/usr/bin/env python3
"""Soft-prune old posts for one expert while preserving old posts linked by newer ones."""

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_sqlite_db_path

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="scripts.clean_old_posts",
)
DEFAULT_DB_PATH = get_sqlite_db_path(BACKEND_DIR)
DEFAULT_BACKUP_DIR = BACKEND_DIR / "data" / "backups"


@dataclass
class PrunePlan:
    total_posts: int
    new_posts: int
    old_posts: int
    keep_posts: int
    delete_posts: int
    delete_comments: int
    keep_comments: int
    delete_drift: int
    keep_drift: int
    delete_links: int
    delete_vec_posts: int
    keep_vec_posts: int


def chunked(items: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def enable_foreign_keys(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def load_sqlite_vec_if_needed(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec before touching vec0 virtual tables."""
    if not table_exists(conn, "vec_posts"):
        return

    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except Exception as exc:
        raise RuntimeError(
            "vec_posts exists but sqlite_vec could not be loaded; aborting prune "
            "to avoid leaving stale vector rows."
        ) from exc
    finally:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass


def create_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.name}.soft-prune.{timestamp}.backup"
    shutil.copy2(db_path, backup_path)
    return backup_path


def get_post_buckets(
    conn: sqlite3.Connection,
    expert_id: str,
    cutoff_date: str,
    preserve_linked_old: bool,
) -> tuple[list[int], list[int], list[int]]:
    rows = conn.execute(
        """
        SELECT post_id, created_at
        FROM posts
        WHERE expert_id = ?
        """,
        (expert_id,),
    ).fetchall()

    new_post_ids: set[int] = set()
    old_post_ids: set[int] = set()

    for post_id, created_at in rows:
        if created_at and created_at >= cutoff_date:
            new_post_ids.add(post_id)
        else:
            old_post_ids.add(post_id)

    old_posts_to_keep: set[int] = set()
    if preserve_linked_old and new_post_ids and old_post_ids:
        links = conn.execute(
            "SELECT source_post_id, target_post_id FROM links"
        ).fetchall()
        for source_post_id, target_post_id in links:
            if source_post_id in new_post_ids and target_post_id in old_post_ids:
                old_posts_to_keep.add(target_post_id)
            if target_post_id in new_post_ids and source_post_id in old_post_ids:
                old_posts_to_keep.add(source_post_id)

    delete_post_ids = sorted(old_post_ids - old_posts_to_keep)
    keep_post_ids = sorted(old_posts_to_keep)

    return sorted(new_post_ids), keep_post_ids, delete_post_ids


def count_for_posts(
    conn: sqlite3.Connection,
    table: str,
    post_column: str,
    post_ids: list[int],
) -> int:
    if not post_ids:
        return 0

    total = 0
    for batch in chunked(post_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        query = f"SELECT COUNT(*) FROM {table} WHERE {post_column} IN ({placeholders})"
        total += conn.execute(query, batch).fetchone()[0]
    return total


def count_links_touching_posts(conn: sqlite3.Connection, post_ids: list[int]) -> int:
    if not post_ids:
        return 0

    total = 0
    for batch in chunked(post_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        total += conn.execute(
            f"""
            SELECT COUNT(*)
            FROM links
            WHERE source_post_id IN ({placeholders})
               OR target_post_id IN ({placeholders})
            """,
            batch + batch,
        ).fetchone()[0]
    return total


def build_plan(
    conn: sqlite3.Connection,
    expert_id: str,
    cutoff_date: str,
    preserve_linked_old: bool,
) -> tuple[PrunePlan, list[int], list[int], list[int]]:
    new_post_ids, keep_post_ids, delete_post_ids = get_post_buckets(
        conn,
        expert_id,
        cutoff_date,
        preserve_linked_old,
    )
    total_posts = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE expert_id = ?",
        (expert_id,),
    ).fetchone()[0]

    plan = PrunePlan(
        total_posts=total_posts,
        new_posts=len(new_post_ids),
        old_posts=len(keep_post_ids) + len(delete_post_ids),
        keep_posts=len(keep_post_ids),
        delete_posts=len(delete_post_ids),
        delete_comments=count_for_posts(conn, "comments", "post_id", delete_post_ids),
        keep_comments=count_for_posts(conn, "comments", "post_id", keep_post_ids),
        delete_drift=count_for_posts(conn, "comment_group_drift", "post_id", delete_post_ids),
        keep_drift=count_for_posts(conn, "comment_group_drift", "post_id", keep_post_ids),
        delete_links=count_links_touching_posts(conn, delete_post_ids),
        delete_vec_posts=(
            count_for_posts(conn, "vec_posts", "post_id", delete_post_ids)
            if table_exists(conn, "vec_posts")
            else 0
        ),
        keep_vec_posts=(
            count_for_posts(conn, "vec_posts", "post_id", keep_post_ids)
            if table_exists(conn, "vec_posts")
            else 0
        ),
    )

    return plan, new_post_ids, keep_post_ids, delete_post_ids


def print_plan(expert_id: str, cutoff_date: str, plan: PrunePlan) -> None:
    print("=" * 60)
    print("SOFT PRUNE PLAN")
    print("=" * 60)
    print(f"Expert: {expert_id}")
    print(f"Cutoff date: {cutoff_date}")
    print()
    print("Posts:")
    print(f"  Total posts: {plan.total_posts}")
    print(f"  Posts >= cutoff: {plan.new_posts}")
    print(f"  Posts < cutoff: {plan.old_posts}")
    print(f"  Old posts kept via links: {plan.keep_posts}")
    print(f"  Old posts deleted: {plan.delete_posts}")
    print()
    print("Associated data:")
    print(f"  Comments kept with linked old posts: {plan.keep_comments}")
    print(f"  Comments deleted with old posts: {plan.delete_comments}")
    print(f"  Drift records kept with linked old posts: {plan.keep_drift}")
    print(f"  Drift records deleted: {plan.delete_drift}")
    print(f"  Links deleted: {plan.delete_links}")
    print(f"  Vec rows kept with linked old posts: {plan.keep_vec_posts}")
    print(f"  Vec rows deleted: {plan.delete_vec_posts}")
    print("=" * 60)


def rebuild_vec_posts_excluding(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    """Rebuild vec_posts when sqlite-vec direct DELETE is ineffective.

    Existing production DBs were populated with sqlite-vec rows where direct
    DELETE by the declared primary key can be a no-op. Rebuilding the virtual
    table from its readable rows is deterministic and keeps embeddings for all
    remaining posts without re-calling the embedding API.
    """
    if not post_ids or not table_exists(conn, "vec_posts"):
        return

    delete_ids = set(post_ids)
    rows = conn.execute(
        "SELECT post_id, embedding, expert_id, created_at FROM vec_posts"
    ).fetchall()
    keep_rows = [row for row in rows if row[0] not in delete_ids]

    conn.execute("DROP TABLE vec_posts")
    conn.execute(
        """
        CREATE VIRTUAL TABLE vec_posts USING vec0(
            post_id INTEGER PRIMARY KEY,
            embedding float[768],
            expert_id TEXT PARTITION KEY,
            created_at TEXT
        )
        """
    )
    for batch in chunked(keep_rows, 500):
        conn.executemany(
            """
            INSERT INTO vec_posts (post_id, embedding, expert_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            batch,
        )


def delete_vec_posts(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    if not post_ids or not table_exists(conn, "vec_posts"):
        return

    for batch in chunked(post_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        conn.execute(
            f"DELETE FROM vec_posts WHERE post_id IN ({placeholders})",
            batch,
        )

    remaining = count_for_posts(conn, "vec_posts", "post_id", post_ids)
    if remaining:
        rebuild_vec_posts_excluding(conn, post_ids)
        remaining_after_rebuild = count_for_posts(
            conn, "vec_posts", "post_id", post_ids
        )
        if remaining_after_rebuild:
            raise RuntimeError(
                f"Failed to delete {remaining_after_rebuild} stale vec_posts rows"
            )


def delete_posts(conn: sqlite3.Connection, post_ids: list[int]) -> None:
    delete_vec_posts(conn, post_ids)

    for batch in chunked(post_ids, 500):
        placeholders = ",".join("?" for _ in batch)

        conn.execute(
            f"DELETE FROM comment_group_drift WHERE post_id IN ({placeholders})",
            batch,
        )
        conn.execute(
            f"DELETE FROM comments WHERE post_id IN ({placeholders})",
            batch,
        )
        conn.execute(
            f"DELETE FROM links WHERE source_post_id IN ({placeholders}) OR target_post_id IN ({placeholders})",
            batch + batch,
        )
        conn.execute(
            f"DELETE FROM post_embeddings WHERE post_id IN ({placeholders})",
            batch,
        )
        conn.execute(
            f"DELETE FROM posts WHERE post_id IN ({placeholders})",
            batch,
        )


def vacuum_database(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Soft-prune old posts while preserving older posts linked by newer ones."
    )
    parser.add_argument("--expert-id", required=True, help="Expert ID to prune")
    parser.add_argument("--cutoff-date", required=True, help="Keep posts on/after this date (YYYY-MM-DD)")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to SQLite database")
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR), help="Directory for backups")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only; do not modify DB")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument(
        "--no-preserve-linked-old",
        action="store_true",
        help="Delete all old posts before cutoff even if links connect them to newer posts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).resolve()
    backup_dir = Path(args.backup_dir).resolve()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        enable_foreign_keys(conn)
        load_sqlite_vec_if_needed(conn)
        preserve_linked_old = not args.no_preserve_linked_old
        plan, _, _, delete_post_ids = build_plan(
            conn,
            args.expert_id,
            args.cutoff_date,
            preserve_linked_old,
        )
        print_plan(args.expert_id, args.cutoff_date, plan)

        if args.dry_run:
            print("Dry run only. No changes made.")
            return 0

        if plan.delete_posts == 0:
            print("Nothing to delete.")
            return 0

        backup_path = create_backup(db_path, backup_dir)
        print(f"Backup created: {backup_path}")

        if not args.yes:
            confirm = input("Proceed with soft prune? [y/N]: ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return 0

        try:
            conn.execute("BEGIN")
            delete_posts(conn, delete_post_ids)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()

    vacuum_database(db_path)

    verify_conn = sqlite3.connect(db_path)
    try:
        enable_foreign_keys(verify_conn)
        load_sqlite_vec_if_needed(verify_conn)
        plan_after, _, _, _ = build_plan(
            verify_conn,
            args.expert_id,
            args.cutoff_date,
            preserve_linked_old,
        )
        print()
        print("Post-prune check:")
        print(f"  Remaining old posts deletable: {plan_after.delete_posts}")
        print(f"  Preserved linked old posts: {plan_after.keep_posts}")
        print(f"  Remaining total posts: {plan_after.total_posts}")
    finally:
        verify_conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
