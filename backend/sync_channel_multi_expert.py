#!/usr/bin/env python3
"""
Multi-Expert Telegram Channel Sync CLI
Синхронизирует все каналы Telegram для multi-expert системы.

Usage:
    python sync_channel_multi_expert.py [--dry-run] [--depth N]

Examples:
    python sync_channel_multi_expert.py --dry-run    # Preview without saving
    python sync_channel_multi_expert.py              # Run sync for all experts
    python sync_channel_multi_expert.py --depth 5    # Check last 5 posts for comments
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Any
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from data.channel_syncer import TelegramChannelSyncer
from models.base import SessionLocal
from models.post import Post
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_all_experts(db) -> List[Dict[str, str]]:
    """
    Получает всех экспертов из базы данных с их каналами.

    Returns:
        List of dicts: [{'expert_id': str, 'channel_id': str, 'channel_username': str, 'channel_name': str}]
    """
    query = text("""
        SELECT DISTINCT
            p.expert_id,
            p.channel_id,
            p.channel_name,
            MIN(p.telegram_message_id) as min_message_id,
            MAX(p.telegram_message_id) as max_message_id,
            COUNT(*) as post_count
        FROM posts p
        WHERE p.expert_id IS NOT NULL
        GROUP BY p.expert_id, p.channel_id, p.channel_name
        ORDER BY p.expert_id
    """)

    result = db.execute(query)
    experts = []

    # Channel mapping from user provided URLs
    CHANNEL_MAPPING = {
        'refat': 'nobilix',
        'ai_architect': 'the_ai_architect',
        'neuraldeep': 'neuraldeep'
    }

    for row in result.fetchall():
        expert_id, channel_id, channel_name, min_id, max_id, count = row

        # Map expert_id to channel_username
        channel_username = CHANNEL_MAPPING.get(expert_id)
        if not channel_username:
            print(f"⚠️  Unknown channel mapping for expert: {expert_id}")
            continue

        experts.append({
            'expert_id': expert_id,
            'channel_id': channel_id,
            'channel_username': channel_username,
            'channel_name': channel_name,
            'min_message_id': min_id,
            'max_message_id': max_id,
            'post_count': count
        })

    return experts


def run_preflight_checks():
    """
    Run preflight checks before sync.

    Checks:
    1. Telegram session file exists
    2. API credentials in environment

    Raises:
        FileNotFoundError: If session file missing
        EnvironmentError: If required env vars missing
    """
    # Check 1: Session file exists
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_fetcher')
    session_path = Path(f"{session_name}.session")

    if not session_path.exists():
        print("❌ ERROR: Telegram session file not found", file=sys.stderr)
        print(file=sys.stderr)
        print("How to fix:", file=sys.stderr)
        print("1. Run: python -m src.data.telegram_comments_fetcher", file=sys.stderr)
        print("2. Follow interactive prompts to authenticate", file=sys.stderr)
        print("3. Session file will be created automatically", file=sys.stderr)
        print(file=sys.stderr)
        print(f"Expected file: {session_path}", file=sys.stderr)
        sys.exit(1)

    # Check 2: API credentials present
    required_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        print(f"❌ ERROR: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print(file=sys.stderr)
        print("How to fix:", file=sys.stderr)
        print("1. Add to .env file:", file=sys.stderr)
        print("   TELEGRAM_API_ID=12345678", file=sys.stderr)
        print("   TELEGRAM_API_HASH=abcdef...", file=sys.stderr)
        print(file=sys.stderr)
        print("2. Get credentials from: https://my.telegram.org", file=sys.stderr)
        sys.exit(1)

    print("✅ Preflight checks passed", file=sys.stderr)
    print(file=sys.stderr)


def create_pending_drift_records(db: Session, expert_id: str, post_ids: List[int]):
    """
    Создает записи в comment_group_drift с analyzed_by = 'pending' для новых постов.

    Args:
        db: Database session
        expert_id: Expert identifier
        post_ids: List of post IDs needing drift analysis
    """
    for post_id in post_ids:
        # Check if record already exists
        existing = db.execute(text("""
            SELECT 1 FROM comment_group_drift WHERE post_id = :post_id
        """), {"post_id": post_id}).fetchone()

        if not existing:
            # Create new pending record
            db.execute(text("""
                INSERT INTO comment_group_drift
                (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
                VALUES (:post_id, 0, NULL, datetime('now'), 'pending', :expert_id)
            """), {"post_id": post_id, "expert_id": expert_id})


def reset_drift_records_to_pending(db: Session, post_ids: List[int]):
    """
    Сбрасывает существующие drift записи в 'pending' для постов с НОВЫМИ комментариями.

    Args:
        db: Database session
        post_ids: List of post IDs with NEW comments (not all posts with comments)
    """
    if not post_ids:
        return

    placeholders = ','.join([str(pid) for pid in post_ids])
    db.execute(text(f"""
        UPDATE comment_group_drift
        SET analyzed_by = 'pending',
            drift_topics = NULL,
            analyzed_at = datetime('now')
        WHERE post_id IN ({placeholders})
    """))


def print_multi_expert_summary(results: List[Dict[str, Any]], start_time: datetime):
    """Print multi-expert summary to stderr."""
    print(file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print("MULTI-EXPERT SYNC COMPLETE", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    total_new_posts = 0
    total_updated_posts = 0
    total_new_comments = 0
    total_pending_drift = 0
    total_errors = 0
    successful_experts = 0

    for result in results:
        expert_id = result['expert_id']

        if result['success']:
            successful_experts += 1
            print(f"✅ {expert_id}: SUCCESS", file=sys.stderr)
        else:
            print(f"❌ {expert_id}: FAILED", file=sys.stderr)
            total_errors += 1

        print(f"   New posts: {len(result['new_posts'])}", file=sys.stderr)
        if result['new_posts']:
            print(f"   Post IDs: {result['new_posts'][:5]}...", file=sys.stderr)

        print(f"   Updated posts: {len(result['updated_posts'])}", file=sys.stderr)
        if result['updated_posts']:
            print(f"   Post IDs: {result['updated_posts'][:5]}...", file=sys.stderr)

        print(f"   New comments: {result['stats'].get('total_comments', 0)}", file=sys.stderr)
        print(f"   Pending drift: {len(result['new_comment_groups'])}", file=sys.stderr)
        print(file=sys.stderr)

        total_new_posts += len(result['new_posts'])
        total_updated_posts += len(result['updated_posts'])
        total_new_comments += result['stats'].get('total_comments', 0)
        total_pending_drift += len(result['new_comment_groups'])

    print("📈 TOTAL SUMMARY:", file=sys.stderr)
    print(f"   Experts processed: {successful_experts}/{len(results)}", file=sys.stderr)
    print(f"   Total new posts: {total_new_posts}", file=sys.stderr)
    print(f"   Total updated posts: {total_updated_posts}", file=sys.stderr)
    print(f"   Total new comments: {total_new_comments}", file=sys.stderr)
    print(f"   Total pending drift: {total_pending_drift}", file=sys.stderr)

    duration = (datetime.utcnow() - start_time).total_seconds()
    print(f"   Total duration: {duration:.1f}s", file=sys.stderr)

    print("=" * 80, file=sys.stderr)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Sync all Telegram channels for multi-expert system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run          Preview changes without saving
  %(prog)s                    Run sync for all experts
  %(prog)s --depth 5          Check last 5 posts for new comments
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without saving to database'
    )

    parser.add_argument(
        '--depth',
        type=int,
        help='Number of recent posts to check for new comments (overrides default 10)'
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Run preflight checks
    run_preflight_checks()

    # Load configuration from environment
    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_fetcher')

    # Sync depth (override from CLI or use default)
    sync_depth = args.depth or 10

    print("🔄 MULTI-EXPERT TELEGRAM SYNC", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}", file=sys.stderr)
    print(f"Comment depth: {sync_depth} posts", file=sys.stderr)
    print(file=sys.stderr)

    # Get all experts from database
    db = SessionLocal()
    try:
        experts = get_all_experts(db)
        if not experts:
            print("❌ No experts found in database!", file=sys.stderr)
            sys.exit(1)

        print(f"📊 Found {len(experts)} experts:", file=sys.stderr)
        for expert in experts:
            print(f"   • {expert['expert_id']} ({expert['channel_username']}) - {expert['post_count']} posts", file=sys.stderr)
        print(file=sys.stderr)

        # Create syncer
        syncer = TelegramChannelSyncer(
            api_id=api_id,
            api_hash=api_hash,
            session_name=session_name
        )
        syncer.RECENT_POSTS_DEPTH = sync_depth

        # Sync each expert
        results = []
        start_time = datetime.utcnow()

        for i, expert in enumerate(experts, 1):
            print(f"[{i}/{len(experts)}] Syncing expert: {expert['expert_id']}", file=sys.stderr)
            print(f"   Channel: {expert['channel_username']} ({expert['channel_name']})", file=sys.stderr)
            print(f"   Posts: {expert['post_count']} (ID: {expert['min_message_id']}-{expert['max_message_id']})", file=sys.stderr)

            try:
                # Run sync for this expert
                result = await syncer.sync_channel_incremental(
                    channel_username=expert['channel_username'],
                    expert_id=expert['expert_id'],
                    dry_run=args.dry_run
                )

                # Add expert_id to result
                result['expert_id'] = expert['expert_id']

                # Handle drift records if not dry run
                if not args.dry_run and result['success']:
                    # Create pending drift records for new posts
                    if result['new_posts']:
                        # Convert telegram_message_ids to post_ids
                        new_post_ids = db.execute(text("""
                            SELECT post_id FROM posts
                            WHERE expert_id = :expert_id AND telegram_message_id IN ({})
                        """.format(','.join(map(str, result['new_posts'])))),
                        {"expert_id": expert['expert_id']}).fetchall()

                        post_ids = [row[0] for row in new_post_ids]
                        if post_ids:
                            create_pending_drift_records(db, expert['expert_id'], post_ids)
                            print(f"   🎯 Created {len(post_ids)} pending drift records for new posts", file=sys.stderr)

                    # Reset drift records ONLY for posts with NEW comments (saved > 0)
                    # result['stats']['total_comments'] shows newly saved comments
                    if result['stats'].get('total_comments', 0) > 0 and result['updated_posts']:
                        # Find posts that actually got NEW comments (not just checked)
                        posts_with_new_comments = db.execute(text("""
                            SELECT DISTINCT p.post_id
                            FROM posts p
                            WHERE p.expert_id = :expert_id
                              AND p.telegram_message_id IN ({})
                              AND EXISTS (
                                SELECT 1 FROM comments c
                                WHERE c.post_id = p.post_id
                              )
                        """.format(','.join(map(str, result['updated_posts'])))),
                        {"expert_id": expert['expert_id']}).fetchall()

                        post_ids = [row[0] for row in posts_with_new_comments]
                        if post_ids:
                            reset_drift_records_to_pending(db, post_ids)
                            print(f"   🔄 Reset {len(post_ids)} drift records to pending (posts with new comments)", file=sys.stderr)

                    db.commit()

                results.append(result)

                print(f"   ✅ Complete: {len(result['new_posts'])} new posts, {result['stats'].get('total_comments', 0)} new comments", file=sys.stderr)
                print(file=sys.stderr)

            except Exception as e:
                error_msg = f"Sync failed for {expert['expert_id']}: {e}"
                print(f"   ❌ {error_msg}", file=sys.stderr)

                results.append({
                    'expert_id': expert['expert_id'],
                    'success': False,
                    'new_posts': [],
                    'updated_posts': [],
                    'new_comment_groups': [],
                    'stats': {'total_comments': 0},
                    'errors': [error_msg]
                })
                print(file=sys.stderr)

        # Print final summary
        print_multi_expert_summary(results, start_time)

        # Output JSON to stdout (for programmatic parsing)
        final_result = {
            'success': all(r['success'] for r in results),
            'experts_processed': len(results),
            'successful_experts': sum(1 for r in results if r['success']),
            'total_new_posts': sum(len(r['new_posts']) for r in results),
            'total_updated_posts': sum(len(r['updated_posts']) for r in results),
            'total_new_comments': sum(r['stats'].get('total_comments', 0) for r in results),
            'total_pending_drift': sum(len(r['new_comment_groups']) for r in results),
            'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
            'expert_results': results
        }

        print(json.dumps(final_result, indent=2, ensure_ascii=False))

        # Exit with appropriate code
        sys.exit(0 if final_result['success'] else 1)

    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())