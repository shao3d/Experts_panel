#!/usr/bin/env python3
"""
Multi-Expert Telegram Channel Sync CLI
Wrapper around sync_orchestrator service.
"""

import asyncio
import argparse
import sys
import json
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli, run_async

BACKEND_DIR, logger = bootstrap_cli(
    __file__,
    logger_name="cli.sync_channel_multi_expert",
)

from src.services.sync_orchestrator import run_cron_pipeline

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Sync all Telegram channels for multi-expert system',
        formatter_class=argparse.RawDescriptionHelpFormatter
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
    
    # Sync depth (override from CLI or use environment variable or default)
    sync_depth = args.depth or int(os.getenv('SYNC_DEPTH', '10'))

    try:
        result = await run_cron_pipeline(dry_run=args.dry_run, depth=sync_depth)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    run_async(main())
