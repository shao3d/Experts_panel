#!/usr/bin/env python3
"""Run the pending drift analysis cycle from the command line."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import (
    bootstrap_cli,
    require_vertex_runtime,
    run_async,
    set_default_sqlite_database_url,
)

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.run_drift_service",
)
DB_PATH = set_default_sqlite_database_url(BACKEND_DIR)

from src.models.base import SessionLocal
from src.services.drift_scheduler_service import DriftSchedulerService


async def _run_cycle() -> None:
    require_vertex_runtime()

    db = SessionLocal()
    try:
        scheduler = DriftSchedulerService(db)
        await scheduler.run_full_cycle()
    finally:
        db.close()


def main() -> None:
    logger.info("Starting drift analysis service (db=%s)", DB_PATH)

    try:
        run_async(_run_cycle())
    except Exception:
        logger.exception("Fatal error while running drift analysis service")
        raise SystemExit(1) from None

    logger.info("Drift analysis cycle completed successfully")


if __name__ == "__main__":
    main()
