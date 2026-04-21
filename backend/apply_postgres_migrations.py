#!/usr/bin/env python3
"""Apply SQL migrations to a PostgreSQL database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, get_postgres_database_url

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.apply_postgres_migrations",
)


def get_postgres_connection(db_url: str) -> psycopg2.extensions.connection:
    """Connect to PostgreSQL."""
    return psycopg2.connect(db_url)


def apply_migration(pg_conn: psycopg2.extensions.connection, migration_path: Path) -> None:
    """Apply a single SQL migration if it has not been applied yet."""
    migration_name = migration_path.name

    with open(migration_path, "r", encoding="utf-8") as handle:
        migration_sql = handle.read()

    cursor = pg_conn.cursor()

    try:
        cursor.execute(
            """
            SELECT COUNT(*) FROM applied_migrations WHERE migration_name = %s
            """,
            (migration_name,),
        )

        if cursor.fetchone()[0] > 0:
            logger.info("Skipping already applied migration %s", migration_name)
            return

        cursor.execute(migration_sql)
        cursor.execute(
            """
            INSERT INTO applied_migrations (migration_name, applied_at)
            VALUES (%s, NOW())
            """,
            (migration_name,),
        )
        pg_conn.commit()
        logger.info("Applied migration %s", migration_name)

    except Exception:
        pg_conn.rollback()
        logger.exception("Failed to apply migration %s", migration_name)
        raise
    finally:
        cursor.close()


def ensure_migration_table(pg_conn: psycopg2.extensions.connection) -> None:
    """Create the migration tracking table when needed."""
    cursor = pg_conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS applied_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        pg_conn.commit()
        logger.info("Migration tracking table is ready")
    except Exception:
        pg_conn.rollback()
        logger.exception("Failed to create migration tracking table")
        raise
    finally:
        cursor.close()


def apply_migrations(migrations_dir: Path, database_url: str) -> None:
    """Apply all ordered SQL migrations from `migrations_dir`."""
    migration_files = sorted(
        migration
        for migration in migrations_dir.glob("*.sql")
        if migration.name.startswith(("00", "01", "02", "03", "04", "05", "06", "07"))
    )

    if not migration_files:
        raise RuntimeError(f"No migrations found in {migrations_dir}")

    logger.info(
        "Applying %s PostgreSQL migrations from %s",
        len(migration_files),
        migrations_dir,
    )

    pg_conn = get_postgres_connection(database_url)
    try:
        ensure_migration_table(pg_conn)
        for migration_file in migration_files:
            apply_migration(pg_conn, migration_file)
    finally:
        pg_conn.close()

    logger.info("All PostgreSQL migrations applied successfully")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--migrations-dir",
        default=str(BACKEND_DIR / "migrations"),
        help="Directory with ordered .sql migrations",
    )
    parser.add_argument(
        "--postgres-url",
        help="Explicit PostgreSQL URL. Otherwise POSTGRES_DATABASE_URL or DATABASE_URL is used.",
    )
    args = parser.parse_args()

    try:
        database_url = args.postgres_url or get_postgres_database_url()
        apply_migrations(Path(args.migrations_dir).expanduser().resolve(), database_url)
    except Exception:
        logger.exception("PostgreSQL migration run failed")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
