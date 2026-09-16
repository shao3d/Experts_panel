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
    require_openrouter_runtime,
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


async def _run_cycle(expert_ids: list[str] | None = None) -> None:
    require_openrouter_runtime()

    db = SessionLocal()
    try:
        scheduler = DriftSchedulerService(db, expert_ids=expert_ids)
        await scheduler.run_full_cycle()
    finally:
        db.close()


def _resolve_expert_ids(args) -> list[str] | None:
    if args.scope:
        from src.expert_groups import AGENT_CONTEXT_EXPERT_GROUPS, resolve_expert_group

        try:
            return resolve_expert_group(args.scope)
        except KeyError:
            known = ", ".join(sorted(AGENT_CONTEXT_EXPERT_GROUPS))
            raise SystemExit(f"unknown scope group: {args.scope} (known: {known})")
    if args.experts:
        return [item.strip() for item in args.experts.split(",") if item.strip()]
    return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the pending drift analysis cycle")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--scope", help="Only this expert group (e.g. visual)")
    scope.add_argument("--experts", help="Comma-separated expert ids")
    args = parser.parse_args()

    expert_ids = _resolve_expert_ids(args)
    logger.info(
        "Starting drift analysis service (db=%s, scope=%s)",
        DB_PATH,
        ", ".join(expert_ids) if expert_ids else "all",
    )

    try:
        run_async(_run_cycle(expert_ids))
    except Exception:
        logger.exception("Fatal error while running drift analysis service")
        raise SystemExit(1) from None

    logger.info("Drift analysis cycle completed successfully")


if __name__ == "__main__":
    main()
