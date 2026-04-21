#!/usr/bin/env python3
"""Legacy manual script for a one-off user query experiment."""

import asyncio
import sys
import os

sys.path.insert(0, 'src')

import importlib.util
spec = importlib.util.spec_from_file_location("reddit_client", 'src/services/reddit_client.py')
reddit_module = importlib.util.module_from_spec(spec)

class MockModule:
    pass
sys.modules['..config'] = MockModule()
sys.modules['..utils.language_utils'] = MockModule()

spec.loader.exec_module(reddit_module)

async def test_query():
    query = "Как правильно организовать skills для своих ИИ агентов"
    
    print("=" * 70)
    print(f"📝 Original query: {query}")
    print("=" * 70)
    
    # Показываем что делает система
    expanded = reddit_module.expand_query(query)
    subreddits = reddit_module.get_target_subreddits(query)
    
    print(f"\n🔧 Expanded: {expanded}")
    print(f"🎯 Subreddits: {subreddits}")
    print()
    
    # Делаем поиск
    print("🔍 Searching Reddit...")
    result = await reddit_module.search_reddit(query, limit=10)
    
    print(f"\n✅ Found: {result.found_count} posts")
    print(f"⏱️  Time: {result.processing_time_ms}ms")
    print()
    
    # Показываем топ результаты с КОНТЕНТОМ
    print("📊 TOP RESULTS (with content preview):")
    print("=" * 70)
    
    for i, post in enumerate(result.posts[:5], 1):
        print(f"\n{i}. r/{post.subreddit} | {post.score}↑ | {post.num_comments}💬")
        print(f"   Title: {post.title}")
        
        # Показываем контент если есть
        if post.selftext:
            content_preview = post.selftext[:500].replace('\n', ' ')
            print(f"   Content: {content_preview}...")
        else:
            print(f"   Content: [No selftext - link post]")
        print(f"   URL: {post.permalink}")
        print("-" * 70)

if __name__ == "__main__":
    asyncio.run(test_query())
