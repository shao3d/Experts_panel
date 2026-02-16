#!/usr/bin/env python3
"""Test optimized Reddit search."""

import asyncio
import sys
import os

sys.path.insert(0, 'src')

import importlib.util
spec = importlib.util.spec_from_file_location("reddit_client", "src/services/reddit_client.py")
reddit_module = importlib.util.module_from_spec(spec)

class MockModule:
    pass
sys.modules['..config'] = MockModule()
sys.modules['..utils.language_utils'] = MockModule()

spec.loader.exec_module(reddit_module)

search_reddit = reddit_module.search_reddit
expand_query = reddit_module.expand_query
get_target_subreddits = reddit_module.get_target_subreddits


def test_query_expansion():
    """Test query expansion."""
    print("=" * 70)
    print("🧪 TESTING QUERY EXPANSION")
    print("=" * 70)
    
    test_cases = [
        "TTS engines open source",
        "best STT alternative",
        "local LLM setup",
        "RAG implementation guide",
        "selfhosted AI privacy",
    ]
    
    for query in test_cases:
        expanded = expand_query(query)
        subreddits = get_target_subreddits(query)
        print(f"\n📝 Original: '{query}'")
        print(f"   Expanded: '{expanded}'")
        print(f"   Subreddits: {subreddits}")


async def test_optimized_search():
    """Test optimized search with OR operator."""
    print("\n" + "=" * 70)
    print("🔍 TESTING OPTIMIZED OR SEARCH")
    print("=" * 70)
    
    test_queries = [
        "TTS engines",
        "best local LLM",
        "RAG vector database",
    ]
    
    for query in test_queries:
        print(f"\n🔎 Query: '{query}'")
        subreddits = get_target_subreddits(query)
        print(f"   Target subreddits: {subreddits}")
        
        start = asyncio.get_event_loop().time()
        try:
            result = await search_reddit(
                query=query,
                limit=10,
                time_filter="year",
                sort="relevance"
            )
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            
            print(f"   ✅ Found: {result.found_count} posts in {elapsed:.0f}ms")
            print(f"   Query used: {result.query[:60]}...")
            
            # Show distribution across subreddits
            subreddit_counts = {}
            for post in result.posts:
                sub = post.subreddit.lower()
                subreddit_counts[sub] = subreddit_counts.get(sub, 0) + 1
            
            print(f"   Distribution: {dict(sorted(subreddit_counts.items(), key=lambda x: -x[1])[:3])}")
            
        except Exception as e:
            elapsed = (asyncio.get_event_loop().time() - start) * 1000
            print(f"   ❌ Error after {elapsed:.0f}ms: {e}")
        
        await asyncio.sleep(2)


async def test_adaptive_sort():
    """Test adaptive sort strategy."""
    print("\n" + "=" * 70)
    print("📊 TESTING ADAPTIVE SORT STRATEGY")
    print("=" * 70)
    
    # These should trigger 'top' sort
    quality_queries = [
        "best TTS engine",
        "top LLM models",
        "ollama vs lm studio",
        "recommended vector database",
    ]
    
    for query in quality_queries:
        expanded = expand_query(query)
        # Check if adaptive sort would trigger
        quality_keywords = ['best', 'top', 'vs', 'comparison', 'alternative', 'recommended']
        would_use_top = any(kw in query.lower() for kw in quality_keywords)
        
        print(f"\n📝 '{query}'")
        print(f"   Expanded: '{expanded[:50]}...'")
        print(f"   Would use 'top' sort: {would_use_top}")


async def main():
    test_query_expansion()
    await test_optimized_search()
    test_adaptive_sort()
    
    print("\n" + "=" * 70)
    print("✅ OPTIMIZATION TESTING COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
