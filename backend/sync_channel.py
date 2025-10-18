#!/usr/bin/env python3
"""
Telegram Channel Sync CLI
Synchronizes Telegram channel with local database.

Usage:
    python sync_channel.py [--dry-run] [--depth N]

Examples:
    python sync_channel.py --dry-run          # Preview without saving
    python sync_channel.py                    # Run sync
    python sync_channel.py --depth 5          # Check last 5 posts for comments
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from data.channel_syncer import TelegramChannelSyncer


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
    required_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'TELEGRAM_CHANNEL']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        print(f"❌ ERROR: Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print(file=sys.stderr)
        print("How to fix:", file=sys.stderr)
        print("1. Add to .env file:", file=sys.stderr)
        print("   TELEGRAM_API_ID=12345678", file=sys.stderr)
        print("   TELEGRAM_API_HASH=abcdef...", file=sys.stderr)
        print("   TELEGRAM_CHANNEL=nobilix", file=sys.stderr)
        print(file=sys.stderr)
        print("2. Get credentials from: https://my.telegram.org", file=sys.stderr)
        sys.exit(1)

    print("✅ Preflight checks passed", file=sys.stderr)
    print(file=sys.stderr)


def print_summary(result: dict):
    """Print human-readable summary to stderr."""
    print(file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("SYNC COMPLETE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if result['success']:
        print(f"✅ Status: Success", file=sys.stderr)
    else:
        print(f"❌ Status: Failed", file=sys.stderr)

    print(file=sys.stderr)
    print(f"📊 Results:", file=sys.stderr)
    print(f"   New posts: {len(result['new_posts'])}", file=sys.stderr)
    if result['new_posts']:
        print(f"   Post IDs: {result['new_posts']}", file=sys.stderr)

    print(f"   Updated posts: {len(result['updated_posts'])}", file=sys.stderr)
    if result['updated_posts']:
        print(f"   Post IDs: {result['updated_posts']}", file=sys.stderr)

    print(file=sys.stderr)
    print(f"🎯 Drift Analysis:", file=sys.stderr)
    print(f"   New comment groups: {len(result['new_comment_groups'])}", file=sys.stderr)
    if result['new_comment_groups']:
        print(f"   Post IDs: {result['new_comment_groups'][:10]}", file=sys.stderr)
        if len(result['new_comment_groups']) > 10:
            print(f"   ... and {len(result['new_comment_groups']) - 10} more", file=sys.stderr)

    stats = result.get('stats', {})
    print(file=sys.stderr)
    print(f"📈 Stats:", file=sys.stderr)
    print(f"   Total comments: {stats.get('total_comments', 0)}", file=sys.stderr)
    print(f"   Duration: {stats.get('duration_seconds', 0):.1f}s", file=sys.stderr)

    if result.get('errors'):
        print(file=sys.stderr)
        print(f"⚠️  Errors:", file=sys.stderr)
        for error in result['errors']:
            print(f"   - {error}", file=sys.stderr)

    print("=" * 60, file=sys.stderr)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Sync Telegram channel with local database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run          Preview changes without saving
  %(prog)s                    Run sync and save to database
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
        help='Number of recent posts to check for new comments (overrides SYNC_DEPTH env var)'
    )

    parser.add_argument(
        '--expert-id',
        type=str,
        default='refat',
        help='Expert identifier for posts (default: refat)'
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Run preflight checks
    run_preflight_checks()

    # Load configuration from environment
    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    channel_username = os.getenv('TELEGRAM_CHANNEL')
    session_name = os.getenv('TELEGRAM_SESSION_NAME', 'telegram_fetcher')

    # Sync depth (override from CLI or use env var or default)
    if args.depth:
        sync_depth = args.depth
    else:
        sync_depth = int(os.getenv('SYNC_DEPTH', '3'))

    # Create syncer
    syncer = TelegramChannelSyncer(
        api_id=api_id,
        api_hash=api_hash,
        session_name=session_name
    )

    # Override depth
    syncer.RECENT_POSTS_DEPTH = sync_depth

    # Run sync
    result = await syncer.sync_channel_incremental(
        channel_username=channel_username,
        expert_id=args.expert_id,  # Use CLI argument or default
        dry_run=args.dry_run
    )

    # Output JSON to stdout (for programmatic parsing)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Output summary to stderr (for human reading)
    print_summary(result)

    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    asyncio.run(main())
