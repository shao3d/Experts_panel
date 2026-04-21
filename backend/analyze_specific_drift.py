#!/usr/bin/env python3
"""Analyze drift for a single post from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

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
    logger_name="cli.analyze_specific_drift",
)
DB_PATH = set_default_sqlite_database_url(BACKEND_DIR)

from src.models.base import SessionLocal
from src.services.drift_scheduler_service import DriftSchedulerService


async def analyze_single_post(post_id: int) -> None:
    require_vertex_runtime()

    logger.info("Analyzing drift for post_id=%s (db=%s)", post_id, DB_PATH)

    db = SessionLocal()
    try:
        service = DriftSchedulerService(db)

        row = db.execute(
            text(
                """
                SELECT
                    cgd.post_id,
                    p.message_text AS post_text
                FROM comment_group_drift cgd
                JOIN posts p ON cgd.post_id = p.post_id
                WHERE cgd.post_id = :post_id
                """
            ),
            {"post_id": post_id},
        ).fetchone()

        if not row:
            logger.error("Post %s not found in comment_group_drift", post_id)
            raise SystemExit(1)

        comments = db.execute(
            text(
                """
                SELECT author_name, comment_text
                FROM comments
                WHERE post_id = :post_id
                ORDER BY created_at ASC
                """
            ),
            {"post_id": post_id},
        ).fetchall()

        comments_list = [{"author": c.author_name, "text": c.comment_text} for c in comments]
        logger.info("Loaded %s comments for post_id=%s", len(comments_list), post_id)

        if not comments_list:
            logger.warning("No comments found for post_id=%s; skipping drift analysis", post_id)
            return

        result = await service.analyze_drift_async(row.post_text, comments_list)
        service.update_group_status(post_id, result)

        logger.info(
            "Drift analysis complete for post_id=%s has_drift=%s topics=%s",
            post_id,
            result.get("has_drift"),
            len(result.get("drift_topics") or []),
        )

        for topic in result.get("drift_topics") or []:
            logger.info("Topic: %s | Context: %s", topic.get("topic"), topic.get("context"))

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("post_id", type=int, help="Internal post_id from comment_group_drift")
    args = parser.parse_args()

    try:
        run_async(analyze_single_post(args.post_id))
    except SystemExit:
        raise
    except Exception:
        logger.exception("Failed to analyze drift for post_id=%s", args.post_id)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
