#!/usr/bin/env python3
"""Test with translated query."""

import asyncio
import sys
sys.path.insert(0, 'src')

import importlib.util
spec = importlib.util.spec_from_file_location("reddit_client", 'src/services/reddit_client.py')
reddit_module = importlib.util.module_from_spec(spec)

class MockModule:
    pass
sys.modules['..config'] = MockModule()
sys.modules['..utils.language_utils'] = MockModule()

spec.loader.exec_module(reddit_module)

async def test():
    # Тестируем разные варианты перевода
    queries = [
        "AI agent skills organization",
        "how to organize AI agent skills", 
        "MCP server skills configuration",
        "Claude Code skills setup",
        "AI assistant tool organization",
        "agent capabilities structure",
    ]
    
    for query in queries:
        print(f"\n{'='*70}")
        print(f"🔍 Query: {query}")
        print('='*70)
        
        expanded = reddit_module.expand_query(query)
        subreddits = reddit_module.get_target_subreddits(query)
        
        print(f"Expanded: {expanded[:60]}...")
        print(f"Subreddits: {subreddits}")
        
        result = await reddit_module.search_reddit(query, limit=8)
        print(f"Found: {result.found_count} posts in {result.processing_time_ms}ms")
        
        if result.posts:
            print("\nTop 3:")
            for i, post in enumerate(result.posts[:3], 1):
                content = post.selftext[:300] if post.selftext else "[link post]"
                print(f"  {i}. r/{post.subreddit}: {post.title[:50]}...")
                print(f"     Content: {content[:200]}...")
        
        await asyncio.sleep(2)

asyncio.run(test())
