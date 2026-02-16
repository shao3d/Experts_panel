#!/usr/bin/env python3
"""Test Reddit API with different queries."""

import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
sys.path.insert(0, 'src')

import importlib.util
spec = importlib.util.spec_from_file_location("reddit_client", "src/services/reddit_client.py")
reddit_module = importlib.util.module_from_spec(spec)

# Mock imports
class MockModule:
    pass
sys.modules['..config'] = MockModule()
sys.modules['..utils.language_utils'] = MockModule()

spec.loader.exec_module(reddit_module)
search_reddit = reddit_module.search_reddit
get_target_subreddits = reddit_module.get_target_subreddits


async def test_multiple_queries():
    """Test different queries."""
    
    test_cases = [
        # (description, query)
        ("TTS/STT (RU translated)", "TTS STT engines 2024"),
        ("Local LLM", "local LLM ollama setup"),
        ("Voice recognition", "voice recognition open source"),
        ("Hallucinations", "LLM hallucination fix reduce"),
    ]
    
    for desc, query in test_cases:
        print("=" * 70)
        print(f"🔍 {desc}")
        print(f"   Query: '{query}'")
        
        subreddits = get_target_subreddits(query)
        print(f"   Target: {subreddits}")
        print()
        
        try:
            result = await search_reddit(
                query=query,
                limit=5,
                time_filter="year",
                sort="relevance"
            )
            
            print(f"✅ Found {result.found_count} posts in {result.processing_time_ms}ms")
            for i, post in enumerate(result.posts[:3], 1):
                print(f"   {i}. r/{post.subreddit}: {post.title[:50]}... ({post.score}↑)")
            print()
            
        except Exception as e:
            print(f"❌ Error: {e}\n")
        
        await asyncio.sleep(2)  # Rate limiting between requests


if __name__ == "__main__":
    asyncio.run(test_multiple_queries())
