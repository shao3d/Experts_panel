#!/usr/bin/env python3
"""Test actual Reddit API search."""

import asyncio
import sys
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Import only reddit_client (avoiding other service imports)
sys.path.insert(0, 'src')

# Manual import to avoid relative import issues
import importlib.util
spec = importlib.util.spec_from_file_location("reddit_client", "src/services/reddit_client.py")
reddit_module = importlib.util.module_from_spec(spec)

# Need to mock the imports that reddit_client needs
import asyncpraw
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# Set up module
datetime_module = type(sys)('datetime')
datetime_module.datetime = datetime
sys.modules['datetime'] = datetime_module

# Mock the relative imports
class MockModule:
    pass

sys.modules['..config'] = MockModule()
sys.modules['..utils.language_utils'] = MockModule()

# Now load
spec.loader.exec_module(reddit_module)

search_reddit = reddit_module.search_reddit
get_target_subreddits = reddit_module.get_target_subreddits


async def test_real_search():
    """Test real Reddit API search."""
    print("=" * 70)
    print("🔍 Testing REAL Reddit API Search")
    print("=" * 70)
    
    query = "TTS engines text to speech"
    print(f"\n📝 Query: '{query}'")
    
    # Show which subreddits will be targeted
    subreddits = get_target_subreddits(query)
    print(f"🎯 Target subreddits: {subreddits}")
    print(f"⏳ Searching... (this may take 10-20 seconds)\n")
    
    try:
        result = await search_reddit(
            query=query,
            limit=10,
            time_filter="year",
            sort="relevance"
        )
        
        print(f"✅ SUCCESS! Found {result.found_count} posts")
        print(f"   Processing time: {result.processing_time_ms}ms")
        print()
        
        # Show top posts
        print("📊 Top posts:")
        for i, post in enumerate(result.posts[:5], 1):
            print(f"\n{i}. [{post.subreddit}] {post.title[:60]}...")
            print(f"   Score: {post.score}↑ | Comments: {post.num_comments}💬")
            print(f"   Link: https://reddit.com{post.permalink}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_real_search())
