#!/usr/bin/env python3
"""Backfill drift_embedding for existing comment_group_drift rows.

Idempotent: skips rows where drift_embedding is already populated.
Run this once after deploying migration 024 to enable the fast embedding-based
drift_scoring path (replaces 130s LLM chunked scoring with ~1ms cosine similarity).

Usage:
    python -m backend.scripts.maintenance.backfill_drift_embeddings
    python -m backend.scripts.maintenance.backfill_drift_embeddings --limit 100
    python -m backend.scripts.maintenance.backfill_drift_embeddings --batch-size 10
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

# Make the backend package importable when run as a script
BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from src.models.base import SessionLocal  # noqa: E402
from src.services.embedding_service import get_embedding_service  # noqa: E402
from src.services.comment_group_map_service import (  # noqa: E402
    build_drift_text,
    _normalize_embedding_to_blob,
)

logger = logging.getLogger(__name__)


def _fetch_pending_batch(db: Session, batch_size: int) -> List[Tuple[int, str]]:
    """Fetch a batch of un-embedded drift groups (id, drift_topics_json)."""
    rows = db.execute(
        text(
            """
            SELECT id, drift_topics
            FROM comment_group_drift
            WHERE has_drift = 1
              AND drift_topics IS NOT NULL
              AND drift_embedding IS NULL
            ORDER BY id ASC
            LIMIT :limit
            """
        ),
        {"limit": batch_size},
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


async def _embed_and_store_batch(
    db: Session, rows: List[Tuple[int, str]], embedding_service
) -> int:
    """Build texts, embed in parallel, store BLOBs. Returns count of rows written."""
    if not rows:
        return 0

    # Build text representations; skip rows with empty text
    valid: List[Tuple[int, str]] = []
    for row_id, drift_topics_json in rows:
        text_repr = build_drift_text(drift_topics_json)
        if text_repr:
            valid.append((row_id, text_repr))

    if not valid:
        # Nothing to embed in this batch (all rows had empty drift text)
        return 0

    texts = [t for _, t in valid]
    embeddings: List[List[float]] = await embedding_service.embed_batch(
        texts, task_type="RETRIEVAL_DOCUMENT"
    )

    for (row_id, _), embedding in zip(valid, embeddings):
        if not embedding:
            continue
        # Storage contract: stored vectors must be unit-length so
        # _score_by_embedding can skip matrix normalize on read.
        try:
            blob = _normalize_embedding_to_blob(embedding)
        except ValueError as norm_exc:
            logger.warning("Skipping row %s: %s", row_id, norm_exc)
            continue
        db.execute(
            text(
                """
                UPDATE comment_group_drift
                SET drift_embedding = :blob
                WHERE id = :id
                """
            ),
            {"blob": blob, "id": row_id},
        )

    db.commit()
    return len(valid)


async def run_backfill(limit: int, batch_size: int) -> int:
    db = SessionLocal()
    embedding_service = get_embedding_service()
    total = 0
    try:
        while True:
            if limit and total >= limit:
                break
            remaining = (limit - total) if limit else batch_size
            this_batch = min(batch_size, remaining)
            rows = _fetch_pending_batch(db, this_batch)
            if not rows:
                break
            n = await _embed_and_store_batch(db, rows, embedding_service)
            if n == 0:
                # Avoid infinite loop if a batch produced no writes
                break
            total += n
            logger.info(
                "Backfilled %s drift embeddings (latest batch: %s rows)",
                total,
                n,
            )
    finally:
        db.close()
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill drift_embedding for existing drift groups"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Max rows to process (0 = all)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50, help="Rows per embed_batch call"
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.info(
        "Starting drift_embedding backfill (limit=%s, batch_size=%s)",
        args.limit or "all",
        args.batch_size,
    )

    total = asyncio.run(run_backfill(args.limit, args.batch_size))
    logger.info("✅ Backfill complete: %s rows processed", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
