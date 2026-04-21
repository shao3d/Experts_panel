#!/usr/bin/env python3
"""Synchronize data from the local SQLite database into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict

import psycopg2

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (
    bootstrap_cli,
    get_postgres_database_url,
    get_sqlite_db_path,
)

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.sync_to_postgres",
)


def get_sqlite_connection(db_path: str | Path) -> sqlite3.Connection:
    """Connect to the source SQLite database."""
    return sqlite3.connect(str(db_path))


def get_postgres_connection(db_url: str) -> psycopg2.extensions.connection:
    """Connect to PostgreSQL."""
    return psycopg2.connect(db_url)


def copy_table_data(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg2.extensions.connection,
    table_name: str,
    column_mapping: Dict[str, str] | None = None,
) -> None:
    """Copy data from a SQLite table into PostgreSQL."""
    cursor = pg_conn.cursor()

    try:
        cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        pg_conn.commit()

        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()

        if not rows:
            logger.info("Table %s is empty; skipping", table_name)
            return

        columns = [description[0] for description in sqlite_cursor.description]
        if column_mapping:
            columns = [column_mapping.get(col, col) for col in columns]

        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        cursor.executemany(sql, rows)
        pg_conn.commit()

        logger.info("Copied %s rows into %s", len(rows), table_name)

    except Exception:
        pg_conn.rollback()
        logger.exception("Failed to copy table %s", table_name)
        raise
    finally:
        cursor.close()


def copy_posts(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg2.extensions.connection,
) -> None:
    """Copy the `posts` table with its explicit column order."""
    cursor = pg_conn.cursor()

    try:
        cursor.execute("TRUNCATE TABLE posts CASCADE")
        pg_conn.commit()

        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(
            """
            SELECT post_id, telegram_message_id, message_text, author_name, created_at,
                   channel_id, channel_username, expert_id, channel_name, author_id,
                   edited_at, view_count, forward_count, reply_count, media_metadata,
                   is_forwarded, forward_from_channel
            FROM posts
            """
        )
        rows = sqlite_cursor.fetchall()

        if not rows:
            logger.info("Table posts is empty; skipping")
            return

        sql = """
            INSERT INTO posts (
                post_id, telegram_message_id, message_text, author_name, created_at,
                channel_id, channel_username, expert_id, channel_name, author_id,
                edited_at, view_count, forward_count, reply_count, media_metadata,
                is_forwarded, forward_from_channel
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(sql, rows)
        pg_conn.commit()

        logger.info("Copied %s rows into posts", len(rows))

    except Exception:
        pg_conn.rollback()
        logger.exception("Failed to copy table posts")
        raise
    finally:
        cursor.close()


def copy_comment_group_drift(
    sqlite_conn: sqlite3.Connection,
    pg_conn: psycopg2.extensions.connection,
) -> None:
    """Copy `comment_group_drift` while normalizing JSON payloads."""
    cursor = pg_conn.cursor()

    try:
        cursor.execute("TRUNCATE TABLE comment_group_drift")
        pg_conn.commit()

        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(
            """
            SELECT post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id
            FROM comment_group_drift
            """
        )
        rows = sqlite_cursor.fetchall()

        if not rows:
            logger.info("Table comment_group_drift is empty; skipping")
            return

        processed_rows = []
        for row in rows:
            post_id, has_drift, drift_topics_json, analyzed_at, analyzed_by, expert_id = row
            drift_topics = json.loads(drift_topics_json) if drift_topics_json else None
            processed_rows.append(
                (
                    post_id,
                    has_drift,
                    json.dumps(drift_topics) if drift_topics else None,
                    analyzed_at,
                    analyzed_by,
                    expert_id,
                )
            )

        cursor.executemany(
            """
            INSERT INTO comment_group_drift (
                post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            processed_rows,
        )
        pg_conn.commit()

        logger.info("Copied %s rows into comment_group_drift", len(processed_rows))

    except Exception:
        pg_conn.rollback()
        logger.exception("Failed to copy table comment_group_drift")
        raise
    finally:
        cursor.close()


def sync_database(sqlite_path: Path, database_url: str) -> None:
    """Sync the local SQLite DB into PostgreSQL in dependency-safe order."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    logger.info("Starting SQLite -> PostgreSQL sync")
    logger.info("SQLite source: %s", sqlite_path)

    sqlite_conn = get_sqlite_connection(sqlite_path)
    pg_conn = get_postgres_connection(database_url)

    try:
        tables_to_copy = [
            ("posts", copy_posts),
            ("links", None),
            ("comments", None),
            ("sync_state", None),
            ("comment_group_drift", copy_comment_group_drift),
        ]

        for table_name, copy_function in tables_to_copy:
            logger.info("Syncing table %s", table_name)
            if copy_function:
                copy_function(sqlite_conn, pg_conn)
            else:
                copy_table_data(sqlite_conn, pg_conn, table_name)

    finally:
        sqlite_conn.close()
        pg_conn.close()

    logger.info("SQLite -> PostgreSQL sync completed successfully")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        help="Explicit SQLite DB path. Otherwise SQLITE_DB_PATH or backend/data/experts.db is used.",
    )
    parser.add_argument(
        "--postgres-url",
        help="Explicit PostgreSQL URL. Otherwise POSTGRES_DATABASE_URL or DATABASE_URL is used.",
    )
    args = parser.parse_args()

    try:
        sqlite_path = (
            Path(args.sqlite_path).expanduser().resolve()
            if args.sqlite_path
            else Path(os.getenv("SQLITE_DB_PATH", get_sqlite_db_path(BACKEND_DIR))).expanduser().resolve()
        )
        database_url = args.postgres_url or get_postgres_database_url()
        sync_database(sqlite_path, database_url)
    except Exception:
        logger.exception("SQLite -> PostgreSQL sync failed")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
