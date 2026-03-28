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
from pathlib import Path
from datetime import datetime, timezone

# ─── Path setup ───
BACKEND_DIR = Path(__file__).parent.parent
ENV_PATH = BACKEND_DIR / ".env"
DB_PATH = BACKEND_DIR / "data" / "experts.db"

from dotenv import load_dotenv

load_dotenv(ENV_PATH)

import os

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

sys.path.insert(0, str(BACKEND_DIR))

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

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


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
        WHERE pe.post_id IS NULL
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
        WHERE pe.post_id IS NULL
        AND p.message_text IS NOT NULL
        AND LENGTH(p.message_text) > 30
    """
    result = db.execute(text(sql))
    return result.scalar() or 0


async def embed_batch(posts: list[Post], dry_run: bool = False) -> tuple[int, int]:
    """Embed a batch of posts and save to DB."""
    if not posts:
        return 0, 0

    service = get_embedding_service()
    texts = [p.message_text for p in posts]

    if dry_run:
        logger.info(f"🔍 [DRY-RUN] Would embed {len(posts)} posts")
        return len(posts), 0

    # Generate embeddings via batch API
    try:
        embeddings = await service.embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")
        logger.info(f"✅ Generated {len(embeddings)} embeddings")
    except Exception as e:
        logger.error(f"❌ Batch embedding failed: {e}")
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
                        "created_at": post.created_at.isoformat()
                        if post.created_at
                        else datetime.now(timezone.utc).isoformat(),
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

                embedded += 1

            except Exception as e:
                logger.error(
                    f"❌ Failed to save embedding for post {post.post_id}: {e}"
                )
                errors += 1
                db.rollback()
                continue

        db.commit()
        logger.info(f"✅ Saved {embedded} embeddings ({errors} errors)")
        return embedded, errors

    except Exception as e:
        logger.error(f"❌ Database transaction failed: {e}")
        db.rollback()
        return 0, len(posts)
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
    total_embedded = 0
    total_errors = 0
    batch_num = 0

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

            total_embedded += embedded
            total_errors += errors

            progress.update(
                task,
                description=f"[cyan]Batch {batch_num}: {embedded} embedded, {errors} errors",
            )

            if not dry_run and embedded > 0:
                await asyncio.sleep(delay)

    logger.info(f"\n{'=' * 50}")
    logger.info(f"📊 Total batches: {batch_num}")
    logger.info(f"✅ Total embedded: {total_embedded}")
    logger.info(f"❌ Total errors: {total_errors}")

    return total_embedded, total_errors


def main():
    import argparse

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
    args = parser.parse_args()

    if args.continuous:
        asyncio.run(
            run_continuous(args.batch_size, args.dry_run, args.force, args.delay)
        )
    else:
        asyncio.run(process_batch(args.batch_size, args.dry_run, args.force))


if __name__ == "__main__":
    main()
