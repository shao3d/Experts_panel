 #!/usr/bin/env python3
"""Enrich posts with metadata keywords via LLM.

Manually-run script that generates bilingual metadata for posts that don't have it.
This metadata powers the Super-Passport FTS5 search feature.

Usage (run from project root):
    python backend/scripts/enrich_post_metadata.py [--batch-size N] [--dry-run]

Examples:
    python backend/scripts/enrich_post_metadata.py                   # Default batch (50)
    python backend/scripts/enrich_post_metadata.py --batch-size 10   # Small test batch
    python backend/scripts/enrich_post_metadata.py --dry-run          # Preview only
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from json_repair import repair_json

# ─── Path setup (CRITICAL: must be BEFORE any src imports) ───
# Script lives in backend/scripts/ — compute backend dir from here
BACKEND_DIR = Path(__file__).parent.parent
ENV_PATH = BACKEND_DIR / ".env"
DB_PATH = BACKEND_DIR / "data" / "experts.db"

# Load .env from backend/ (not CWD!) — same pattern as analyze_drift.py
from dotenv import load_dotenv
load_dotenv(ENV_PATH)

# Override DATABASE_URL to absolute path (CRITICAL!)
# .env has relative path "sqlite:///data/experts.db" which resolves differently
# depending on CWD. Force absolute path to the correct DB in backend/data/.
import os
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

# Add backend to path
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func
from src.models.base import SessionLocal
from src.models.post import Post
from src.services.google_ai_studio_client import create_google_ai_studio_client
from src.config import METADATA_MODEL, METADATA_BATCH_SIZE

# ─── Logging setup ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "metadata_prompt.txt"


async def generate_metadata(client, post_text: str) -> dict:
    """Generate metadata for a single post."""
    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.replace("{post_text}", post_text)

    response = await client.chat_completions_create(
        model=METADATA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=250  # Increased for structured JSON with arrays
    )

    raw_content = response.choices[0].message.content.strip()

    # Parse JSON (handle markdown code blocks)
    if raw_content.startswith("```"):
        lines = raw_content.split("\n")
        raw_content = "\n".join(lines[1:-1])

    # Use json_repair to handle common LLM JSON issues:
    # - Single quotes instead of double quotes
    # - Trailing commas
    # - Missing quotes on keys
    # - Unquoted string values
    # NOTE: repair_json returns a string, so we need json.loads() after
    fixed_json = repair_json(raw_content)
    return json.loads(fixed_json)


async def enrich_batch(batch_size: int = None, dry_run: bool = False):
    """Enrich a batch of posts."""
    db = SessionLocal()
    client = create_google_ai_studio_client()

    batch = batch_size or METADATA_BATCH_SIZE

    try:
        # CRITICAL: Only enrich posts with meaningful text (>30 chars)
        # Media-only posts would generate hallucinated keywords and waste LLM tokens
        # Exclude video_hub segments — they use a separate pipeline that bypasses FTS5
        posts = db.query(Post).filter(
            Post.post_metadata.is_(None),
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30,
            Post.expert_id != "video_hub"
        ).limit(batch).all()

        pending_total = db.query(func.count(Post.post_id)).filter(
            Post.post_metadata.is_(None),
            Post.message_text.isnot(None),
            func.length(Post.message_text) > 30,
            Post.expert_id != "video_hub"
        ).scalar() or 0

        if not posts:
            logger.info("✅ No posts to enrich. All done!")
            return 0

        logger.info(f"📋 Enriching {len(posts)} posts (total pending: {pending_total}, model: {METADATA_MODEL})")
        if dry_run:
            logger.info("🔍 DRY-RUN mode: no changes will be written")

        enriched = 0
        errors = 0
        for i, post in enumerate(posts, 1):
            try:
                if dry_run:
                    logger.info(f"  [{i}/{len(posts)}] [DRY-RUN] Post {post.post_id}: '{post.message_text[:60]}...'")
                    enriched += 1
                    continue

                metadata = await generate_metadata(client, post.message_text)
                post.post_metadata = json.dumps(metadata, ensure_ascii=False)
                post.metadata_generated_at = datetime.utcnow()
                db.commit()
                enriched += 1

                keywords_preview = metadata.get('keywords', '')[:60]
                logger.info(f"  [{i}/{len(posts)}] ✅ Post {post.post_id}: {metadata.get('primary_topic', '?')} → {keywords_preview}...")
                await asyncio.sleep(0.5)  # Rate limit protection
            except json.JSONDecodeError as e:
                errors += 1
                logger.warning(f"  [{i}/{len(posts)}] ❌ Post {post.post_id}: JSON error - {e}")
                db.rollback()
                continue
            except Exception as e:
                errors += 1
                logger.error(f"  [{i}/{len(posts)}] ❌ Post {post.post_id}: {e}")
                db.rollback()
                continue

        logger.info(f"{'🔍 DRY-RUN' if dry_run else '✅'} Batch complete: {enriched}/{len(posts)} enriched, {errors} errors, {pending_total - enriched} remaining")
        return enriched, errors
    finally:
        db.close()


async def run_continuous(batch_size: int = None, dry_run: bool = False, delay: float = 2.0):
    """Run enrichment continuously until all posts are processed."""
    total_enriched = 0
    total_errors = 0
    batch_num = 0

    while True:
        batch_num += 1
        logger.info(f"\n{'='*50} Batch #{batch_num} {'='*50}")

        enriched, errors = await enrich_batch(batch_size, dry_run)

        if enriched == 0:
            logger.info("🎉 ALL DONE! No more posts to enrich.")
            break

        total_enriched += enriched
        total_errors += errors

        # Brief pause between batches for rate limiting
        if not dry_run and enriched > 0:
            logger.info(f"⏳ Pausing {delay}s before next batch...")
            await asyncio.sleep(delay)

    logger.info(f"\n{'='*50} SUMMARY {'='*50}")
    logger.info(f"📊 Total batches: {batch_num}")
    logger.info(f"✅ Total enriched: {total_enriched}")
    logger.info(f"❌ Total errors: {total_errors}")

    return total_enriched, total_errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enrich posts with metadata for FTS5 search")
    parser.add_argument("--batch-size", type=int, help=f"Number of posts per batch (default: {METADATA_BATCH_SIZE})")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--continuous", action="store_true", help="Run until all posts are enriched")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between batches in seconds (default: 2.0)")
    args = parser.parse_args()

    if args.continuous:
        asyncio.run(run_continuous(args.batch_size, args.dry_run, args.delay))
    else:
        asyncio.run(enrich_batch(args.batch_size, args.dry_run))


if __name__ == "__main__":
    main()
