#!/usr/bin/env python3
"""Comprehensive Reddit search testing with analysis."""

import asyncio
import sys
import os
import logging
from typing import List, Dict, Any
import time

logging.basicConfig(level=logging.INFO, format='%(message)s')
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
get_target_subreddits = reddit_module.get_target_subreddits


# Test categories based on expert channel topics
TEST_QUERIES = {
    "AI/LLM": [
        "best local LLM 2024",
        "ollama vs lm studio",
        "LLM hallucination fix",
        "small LLM raspberry pi",
        "quantized model performance",
    ],
    "TTS/STT/Voice": [
        "TTS text to speech open source",
        "speech recognition self hosted",
        "voice AI local setup",
        "Kokoro TTS quality",
        "whisper STT alternative",
    ],
    "Hardware/GPU": [
        "RTX 4090 LLM inference",
        "AMD GPU ROCm local AI",
        "Apple Silicon ML performance",
        "minimum GPU for LLM",
        "cloud vs local GPU cost",
    ],
    "Programming/Dev": [
        "Python async best practices",
        "Docker AI deployment",
        "Rust vs Python performance",
        "vector database comparison",
        "RAG implementation guide",
    ],
    "Privacy/Security": [
        "self hosted AI privacy",
        "local AI data security",
        "open source LLM safe",
        "AI without cloud",
        "on premise AI deployment",
    ],
}


async def test_query(category: str, query: str) -> Dict[str, Any]:
    """Test single query and return stats."""
    subreddits = get_target_subreddits(query)
    
    start_time = time.time()
    try:
        result = await search_reddit(
            query=query,
            limit=10,
            time_filter="year",
            sort="relevance"
        )
        elapsed = (time.time() - start_time) * 1000
        
        return {
            "category": category,
            "query": query,
            "subreddits": subreddits,
            "found": result.found_count,
            "time_ms": result.processing_time_ms,
            "posts": result.posts,
            "success": True,
            "error": None,
        }
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return {
            "category": category,
            "query": query,
            "subreddits": subreddits,
            "found": 0,
            "time_ms": elapsed,
            "posts": [],
            "success": False,
            "error": str(e),
        }


async def run_all_tests():
    """Run comprehensive test suite."""
    print("=" * 80)
    print("🔬 COMPREHENSIVE REDDIT SEARCH TEST")
    print("=" * 80)
    print(f"Testing {sum(len(v) for v in TEST_QUERIES.values())} queries across {len(TEST_QUERIES)} categories\n")
    
    all_results = []
    
    for category, queries in TEST_QUERIES.items():
        print(f"\n{'='*80}")
        print(f"📁 CATEGORY: {category}")
        print("=" * 80)
        
        for query in queries:
            result = await test_query(category, query)
            all_results.append(result)
            
            status = "✅" if result["success"] else "❌"
            print(f"\n{status} {query[:50]}...")
            print(f"   Target: {result['subreddits']}")
            
            if result["success"]:
                print(f"   Found: {result['found']} posts in {result['time_ms']}ms")
                if result['posts']:
                    top = result['posts'][0]
                    print(f"   Top: r/{top.subreddit} - {top.title[:45]}... ({top.score}↑)")
            else:
                print(f"   ERROR: {result['error'][:60]}...")
            
            # Rate limiting between requests
            await asyncio.sleep(1.5)
    
    return all_results


def analyze_results(results: List[Dict[str, Any]]):
    """Analyze test results and provide insights."""
    print("\n" + "=" * 80)
    print("📊 ANALYSIS & INSIGHTS")
    print("=" * 80)
    
    # Category stats
    category_stats = {}
    for r in results:
        cat = r["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "found": 0, "success": 0, "avg_time": 0}
        category_stats[cat]["total"] += 1
        category_stats[cat]["found"] += r["found"]
        category_stats[cat]["success"] += 1 if r["success"] else 0
        category_stats[cat]["avg_time"] += r["time_ms"]
    
    print("\n📈 Category Performance:")
    for cat, stats in category_stats.items():
        avg_found = stats["found"] / stats["total"]
        avg_time = stats["avg_time"] / stats["total"]
        success_rate = (stats["success"] / stats["total"]) * 100
        print(f"   {cat:20s} | Avg found: {avg_found:5.1f} | Avg time: {avg_time:6.0f}ms | Success: {success_rate:5.1f}%")
    
    # Find underperforming queries
    print("\n⚠️  Underperforming queries (0-1 results):")
    for r in results:
        if r["success"] and r["found"] <= 1:
            print(f"   • [{r['category']}] '{r['query'][:40]}...' - {r['found']} results")
    
    # Best performing queries
    print("\n🏆 Best performing queries (5+ results):")
    for r in results:
        if r["success"] and r["found"] >= 5:
            print(f"   • [{r['category']}] '{r['query'][:40]}...' - {r['found']} results")
    
    # Subreddit usage analysis
    print("\n🎯 Subreddit targeting effectiveness:")
    subreddit_hits = {}
    for r in results:
        if r["success"] and r["posts"]:
            for post in r["posts"]:
                sub = post.subreddit.lower()
                subreddit_hits[sub] = subreddit_hits.get(sub, 0) + 1
    
    top_subreddits = sorted(subreddit_hits.items(), key=lambda x: x[1], reverse=True)[:10]
    for sub, count in top_subreddits:
        print(f"   r/{sub:20s} - {count} posts found")


def generate_optimizations(results: List[Dict[str, Any]]):
    """Generate optimization recommendations."""
    print("\n" + "=" * 80)
    print("💡 OPTIMIZATION RECOMMENDATIONS")
    print("=" * 80)
    
    recommendations = []
    
    # Check for empty subreddits in mapping
    print("\n1. Missing Subreddit Mappings:")
    missing_mappings = [
        ("MCP (Model Context Protocol)", ["LocalLLaMA", "artificial", "MachineLearning"]),
        ("Claude Code", ["ClaudeAI", "LocalLLaMA"]),
        ("Cursor IDE", ["CursorAI", "LocalLLaMA", "artificial"]),
        ("Cline", ["ClaudeAI", "vscode", "LocalLLaMA"]),
        ("OpenAI o3", ["OpenAI", "artificial", "singularity"]),
        ("Gemini Flash", ["GoogleGeminiAI", "artificial", "LocalLLaMA"]),
        ("vLLM", ["LocalLLaMA", "MachineLearning"]),
        ("llama.cpp", ["LocalLLaMA"]),
    ]
    
    for keyword, subs in missing_mappings:
        print(f"   Add: '{keyword}' → {subs}")
        recommendations.append(f"Add mapping: {keyword}")
    
    # Search optimization tips
    print("\n2. Reddit Search Best Practices:")
    tips = [
        "Use 'selftext' search for better content matching (not just titles)",
        "Combine multiple subreddits with OR operator: subreddit:foo OR subreddit:bar",
        "Use 'flair' filtering for specific post types",
        "Consider time_filter='month' for recent discussions",
        "Try sort='top' for quality over quantity",
    ]
    for tip in tips:
        print(f"   • {tip}")
    
    # Query expansion suggestions
    print("\n3. Query Expansion Strategy:")
    expansions = [
        ('TTS', ['text to speech', 'voice synthesis', 'Kokoro', 'Piper']),
        ('STT', ['speech recognition', 'whisper', 'voice to text']),
        ('LLM', ['language model', 'local AI', 'open source LLM']),
        ('RAG', ['retrieval augmented generation', 'vector DB', 'embedding']),
    ]
    
    for term, alternatives in expansions:
        print(f"   '{term}' could expand to: {alternatives}")
    
    return recommendations


async def test_reddit_search_operators():
    """Test different Reddit search strategies."""
    print("\n" + "=" * 80)
    print("🔍 TESTING REDDIT SEARCH OPERATORS")
    print("=" * 80)
    
    strategies = [
        ("Basic", "TTS engines"),
        ("With quotes", '"text to speech" open source'),
        ("Site specific", "TTS engines"),
        ("Exclude", 'TTS engines -premium -subscription'),
    ]
    
    for name, query in strategies:
        print(f"\n📌 Strategy: {name}")
        print(f"   Query: {query}")
        
        try:
            result = await search_reddit(query=query, limit=5, time_filter="year")
            print(f"   ✅ Found: {result.found_count} posts")
            if result.posts:
                print(f"   Top: {result.posts[0].title[:50]}...")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        await asyncio.sleep(2)


async def main():
    # Run comprehensive tests
    results = await run_all_tests()
    
    # Analyze results
    analyze_results(results)
    
    # Generate recommendations
    generate_optimizations(results)
    
    # Test search operators
    await test_reddit_search_operators()
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ TESTING COMPLETE")
    print("=" * 80)
    total_queries = len(results)
    successful = sum(1 for r in results if r["success"])
    total_found = sum(r["found"] for r in results if r["success"])
    avg_time = sum(r["time_ms"] for r in results) / len(results)
    
    print(f"\n📊 Summary:")
    print(f"   Total queries: {total_queries}")
    print(f"   Successful: {successful} ({successful/total_queries*100:.1f}%)")
    print(f"   Total posts found: {total_found}")
    print(f"   Average response time: {avg_time:.0f}ms")
    print(f"   Average posts per query: {total_found/successful:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
