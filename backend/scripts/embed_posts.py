#!/usr/bin/env python3
"""Generate embeddings for posts using Gemini Embedding API.

Offline script for hybrid retrieval.

Usage:
    python backend/scripts/embed_posts.py [--batch-size 50] [--dry-run] [--force]

Examples:
    python backend/scripts/embed_posts.py --dry-run              # Preview
    python backend/scripts/embed_posts.py --batch-size 10        # Test with 10 posts
    python backend/scripts/embed_posts.py --continuous           # Run until complete
    python backend/scripts/embed_posts.py --force                # Re-embed all posts
"""

import asyncio
import json
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.utils.date_utils import format_timestamp, parse_timestamp
from src.cli.bootstrap import (
    bootstrap_cli,
    require_openrouter_runtime,
    set_default_sqlite_database_url,
)

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.embed_posts",
)
DB_PATH = set_default_sqlite_database_url(BACKEND_DIR, force=True)

from sqlalchemy import func, text
from sqlalchemy.orm import Session
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from src.models.base import SessionLocal
from src.models.post import Post
from src.services.embedding_service import get_embedding_service
from src.config import EMBEDDING_DIMENSIONS
from src.utils.video_identity import load_receipt, write_receipt


def get_pending_posts(db: Session, batch_size: int, force: bool = False) -> list[Post]:
    """Get posts that need embeddings."""
    if force:
        # Re-embed all posts with text
        return (
            db.query(Post)
            .filter(Post.message_text.isnot(None), func.length(Post.message_text) > 30)
            .limit(batch_size)
            .all()
        )

    # Only posts without embeddings
    # LEFT JOIN post_embeddings to find unprocessed posts
    sql = """
        SELECT p.* FROM posts p
        LEFT JOIN post_embeddings pe ON p.post_id = pe.post_id
        LEFT JOIN vec_posts vp ON p.post_id = vp.post_id
        WHERE (pe.post_id IS NULL OR vp.post_id IS NULL)
        AND p.message_text IS NOT NULL
        AND LENGTH(p.message_text) > 30
        LIMIT :limit
    """
    result = db.execute(text(sql), {"limit": batch_size})
    post_ids = [row[0] for row in result.fetchall()]

    if not post_ids:
        return []

    # Fetch full posts
    posts = db.query(Post).filter(Post.post_id.in_(post_ids)).all()
    return posts


def get_pending_count(db: Session) -> int:
    """Count posts without embeddings."""
    sql = """
        SELECT COUNT(*) FROM posts p
        LEFT JOIN post_embeddings pe ON p.post_id = pe.post_id
        LEFT JOIN vec_posts vp ON p.post_id = vp.post_id
        WHERE (pe.post_id IS NULL OR vp.post_id IS NULL)
        AND p.message_text IS NOT NULL
        AND LENGTH(p.message_text) > 30
    """
    result = db.execute(text(sql))
    return result.scalar() or 0


async def embed_batch(posts: list[Post], dry_run: bool = False) -> tuple[int, int]:
    """Embed a batch of posts and save to DB."""
    if not posts:
        return 0, 0

    texts = [p.message_text for p in posts]

    if dry_run:
        logger.info(f"🔍 [DRY-RUN] Would embed {len(posts)} posts")
        return len(posts), 0

    service = get_embedding_service()

    # Generate embeddings via batch API
    try:
        embeddings = await service.embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")
        logger.info(f"✅ Generated {len(embeddings)} embeddings")
    except Exception as e:
        logger.error(f"❌ Batch embedding failed: {e}")
        return 0, len(posts)

    if len(embeddings) != len(posts):
        # zip() would silently drop the tail; fail the batch honestly instead.
        logger.error(
            f"❌ Embedding API returned {len(embeddings)} vectors for "
            f"{len(posts)} posts; refusing to save a partial batch"
        )
        return 0, len(posts)

    # Save to database
    db = SessionLocal()
    embedded = 0
    errors = 0

    try:
        for post, embedding in zip(posts, embeddings):
            try:
                # Insert into vec_posts (vector table with metadata)
                # Use INSERT OR REPLACE for idempotency
                parsed_created = parse_timestamp(post.created_at)
                if post.created_at and parsed_created is None:
                    # Present but unparsable: refuse to guess (stamping "now"
                    # would rank the row as brand new) — skip like any bad row.
                    raise ValueError(
                        f"unparsable created_at {post.created_at!r} for post {post.post_id}"
                    )
                vec_sql = """
                    INSERT OR REPLACE INTO vec_posts (post_id, embedding, expert_id, created_at)
                    VALUES (:post_id, vec_f32(:embedding), :expert_id, :created_at)
                """
                db.execute(
                    text(vec_sql),
                    {
                        "post_id": post.post_id,
                        "embedding": json.dumps(embedding),
                        "expert_id": post.expert_id,
                        # Canonical naive-UTC text (same as posts.created_at),
                        # so freshness parsers see one format in every table.
                        "created_at": format_timestamp(
                            parsed_created
                            or datetime.now(timezone.utc).replace(tzinfo=None)
                        ),
                    },
                )

                # Insert metadata record
                meta_sql = """
                    INSERT OR REPLACE INTO post_embeddings 
                    (post_id, embedding_model, dimensions, embedded_at)
                    VALUES (:post_id, :model, :dims, :now)
                """
                db.execute(
                    text(meta_sql),
                    {
                        "post_id": post.post_id,
                        "model": service.model,
                        "dims": EMBEDDING_DIMENSIONS,
                        "now": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Commit per post: one bad row must not roll back its
                # neighbours' already-saved rows (a batch-level rollback after
                # a mid-loop error silently dropped them while the counter
                # still counted them as saved).
                db.commit()
                embedded += 1

            except Exception as e:
                logger.error(
                    f"❌ Failed to save embedding for post {post.post_id}: {e}"
                )
                errors += 1
                db.rollback()
                continue

        logger.info(f"✅ Saved {embedded} embeddings ({errors} errors)")
        return embedded, errors

    except Exception as e:
        logger.error(f"❌ Database transaction failed: {e}")
        db.rollback()
        # Saved rows stay saved (per-post commits); only the unsaved remainder
        # counts as errors — never report zeros over real progress.
        return embedded, (len(posts) - embedded)
    finally:
        db.close()


async def process_batch(
    batch_size: int = 50, dry_run: bool = False, force: bool = False
):
    """Process one batch of posts."""
    db = SessionLocal()

    try:
        pending = get_pending_count(db)
        posts = get_pending_posts(db, batch_size, force)

        if not posts:
            logger.info("✅ No posts to embed. All done!")
            return 0, 0

        logger.info(
            f"📋 Embedding {len(posts)} posts (pending: {pending}, batch: {batch_size})"
        )

        embedded, errors = await embed_batch(posts, dry_run)

        return embedded, errors

    finally:
        db.close()


async def run_continuous(
    batch_size: int = 50, dry_run: bool = False, force: bool = False, delay: float = 0.5
):
    """Run until all posts are embedded."""
    if dry_run or force:
        raise ValueError("continuous cannot be combined with dry_run or force; use one bounded preview/force batch")
    total_embedded = 0
    total_errors = 0
    batch_num = 0
    stalled = 0
    unresolved = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Embedding posts...", total=None)

        while True:
            batch_num += 1

            embedded, errors = await process_batch(batch_size, dry_run, force)

            if embedded == 0 and errors == 0:
                progress.update(task, description="[green]✓ Complete!")
                break
            stalled = stalled + 1 if embedded == 0 else 0

            total_embedded += embedded
            total_errors += errors

            progress.update(
                task,
                description=f"[cyan]Batch {batch_num}: {embedded} embedded, {errors} errors",
            )

            if stalled >= 3:
                unresolved = max(1, errors)
                logger.error("Embedding stopped after three batches without progress; pending posts remain")
                break
            await asyncio.sleep(max(0.0, delay))

    logger.info(f"\n{'=' * 50}")
    logger.info(f"📊 Total batches: {batch_num}")
    logger.info(f"✅ Total embedded: {total_embedded}")
    logger.info(f"❌ Total attempt errors: {total_errors}")
    if total_errors > 0:
        logger.info(
            "ℹ️  These were transient batch failures during processing. "
            "Posts that stayed pending were retried in later passes."
        )

    return total_embedded, unresolved


def verify_receipt_index(receipt_path: Path) -> bool:
    """Record readiness only when every imported source is in FTS and vector search."""
    receipt = load_receipt(receipt_path)
    mids = [int(key.partition(':')[2]) for key in receipt['source_keys']]
    indexed = 0
    with SessionLocal() as db:
        for offset in range(0, len(mids), 500):
            chunk = mids[offset:offset+500]
            bindings = {f'm{i}': value for i, value in enumerate(chunk)}
            placeholders = ','.join(f':m{i}' for i in range(len(chunk)))
            sql = f"""SELECT p.telegram_message_id, COUNT(DISTINCT p.post_id),
                COUNT(DISTINCT pe.post_id), COUNT(DISTINCT vp.post_id), COUNT(DISTINCT f.rowid)
                FROM posts p
                LEFT JOIN post_embeddings pe ON pe.post_id=p.post_id
                LEFT JOIN vec_posts vp ON vp.post_id=p.post_id
                LEFT JOIN posts_fts f ON f.rowid=p.post_id
                WHERE p.expert_id='video_hub' AND p.telegram_message_id IN ({placeholders})
                GROUP BY p.telegram_message_id"""
            indexed += sum(all(count == 1 for count in row[1:]) for row in db.execute(text(sql), bindings))
    ready = indexed == len(mids)
    receipt.update(status='searchable' if ready else 'loaded', indexed_segments=indexed,
                   index_checked_at=datetime.now(timezone.utc).isoformat())
    write_receipt(receipt_path, receipt)
    logger.info("Video import readiness: %s/%s indexed; status=%s", indexed, len(mids), receipt['status'])
    return ready


def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for posts")
    parser.add_argument(
        "--batch-size", type=int, default=50, help="Posts per batch (default: 50)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing"
    )
    parser.add_argument("--force", action="store_true", help="Re-embed all posts")
    parser.add_argument("--continuous", action="store_true", help="Run until complete")
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Delay between batches (default: 0.5s)"
    )
    parser.add_argument('--receipt', type=Path, help='Verify this VideoHub import receipt after indexing')
    args = parser.parse_args()
    if args.continuous and (args.dry_run or args.force):
        parser.error('--continuous cannot be combined with --dry-run or --force')
    if args.receipt and args.dry_run:
        parser.error('--receipt requires actual indexing, not --dry-run')
    if args.batch_size < 1 or args.delay < 0:
        parser.error('batch-size must be positive and delay non-negative')
    if not args.dry_run:
        require_openrouter_runtime()
    logger.info("Embedding script started (db=%s, batch_size=%s)", DB_PATH, args.batch_size)

    if args.continuous:
        _, errors = asyncio.run(
            run_continuous(args.batch_size, args.dry_run, args.force, args.delay)
        )
    else:
        _, errors = asyncio.run(process_batch(args.batch_size, args.dry_run, args.force))
    if errors:
        return 1
    if args.receipt and not verify_receipt_index(args.receipt):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
