"""Quick import runner without interactive prompts."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data.telegram_comments_fetcher import SafeTelegramCommentsFetcher

async def run():
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    channel = os.getenv('TELEGRAM_CHANNEL', 'nobilix')

    if not api_id or not api_hash:
        print("❌ ERROR: Missing TELEGRAM_API_ID or TELEGRAM_API_HASH")
        print("Set them in .env file or environment variables")
        sys.exit(1)

    api_id = int(api_id)

    print(f"\n🚀 Starting import for @{channel}...")

    fetcher = SafeTelegramCommentsFetcher(api_id, api_hash)
    await fetcher.fetch_all_comments(channel)
    
    print("\n✅ Done!")

if __name__ == '__main__':
    asyncio.run(run())
