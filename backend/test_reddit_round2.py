#!/usr/bin/env python3
"""Round 2: Extended Reddit search testing with complex queries."""

import asyncio
import sys
import os
import logging
import time
from typing import List, Dict, Any

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
expand_query = reddit_module.expand_query
get_target_subreddits = reddit_module.get_target_subreddits


# Complex real-world queries that users might ask
COMPLEX_QUERIES = [
    # Multi-concept queries
    ("MCP vs function calling", "Comparison"),
    ("Claude Code Cursor comparison", "Tools comparison"),
    ("llama.cpp vs ollama performance", "Performance"),
    ("vLLM TGI inference engine comparison", "Technical"),
    
    # Specific technical setups
    ("Docker compose LocalAI setup", "Self-hosted"),
    ("Kubernetes LLM deployment", "DevOps"),
    ("nginx reverse proxy ollama", "Infrastructure"),
    ("systemd service auto start LLM", "Linux"),
    
    # Hardware specific
    ("RTX 3060 12GB LLM quantized", "GPU limited"),
    ("Mac M3 Pro MLX performance", "Apple Silicon"),
    ("Intel Arc GPU IPEX LLM", "Intel GPU"),
    ("consumer GPU vs cloud API cost analysis", "Cost"),
    
    # Niche topics
    ("gguf Q4_K_M vs Q5_K_M quality", "Quantization"),
    ("speculative decoding local LLM", "Advanced"),
    ("prompt caching vLLM", "Optimization"),
    ("structured output JSON schema", "Development"),
    
    # Integration questions
    ("n8n nodered automation LLM", "Automation"),
    ("homebridge homekit AI integration", "Smart home"),
    ("obsidian AI plugin local", "Productivity"),
    ("nextcloud AI assistant selfhosted", "Cloud"),
    
    # Troubleshooting
    ("CUDA out of memory LLM fix", "Error fixing"),
    ("slow token generation troubleshooting", "Performance"),
    ("model weights download interrupted resume", "Download"),
    ("permission denied docker socket", "Permissions"),
    
    # Privacy/Security focused
    ("air gapped offline AI deployment", "Security"),
    ("no internet required LLM setup", "Offline"),
    ("local AI HIPAA compliance", "Compliance"),
    ("company data local AI only", "Enterprise"),
]


async def test_complex_query(description: str, query: str) -> Dict:
    """Test a complex query."""
    print(f"\n{'='*70}")
    print(f"🔍 [{description}] {query}")
    print('='*70)
    
    # Show expansion
    expanded = expand_query(query)
    subreddits = get_target_subreddits(query)
    
    print(f"📝 Expanded: {expanded[:70]}...")
    print(f"🎯 Subreddits: {subreddits}")
    
    start = time.time()
    try:
        result = await search_reddit(
            query=query,
            limit=15,
            time_filter="year",
            sort="relevance"
        )
        elapsed = (time.time() - start) * 1000
        
        # Analyze results
        subreddit_dist = {}
        for post in result.posts:
            sub = post.subreddit.lower()
            subreddit_dist[sub] = subreddit_dist.get(sub, 0) + 1
        
        top_subs = sorted(subreddit_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        
        print(f"✅ Found: {result.found_count} posts in {elapsed:.0f}ms")
        print(f"📊 Distribution: {top_subs}")
        
        if result.posts:
            print("\n📌 Top results:")
            for i, post in enumerate(result.posts[:3], 1):
                print(f"   {i}. r/{post.subreddit}: {post.title[:55]}... ({post.score}↑)")
        
        return {
            "query": query,
            "category": description,
            "found": result.found_count,
            "time_ms": elapsed,
            "subreddits": subreddits,
            "distribution": dict(top_subs),
            "success": True,
        }
        
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        print(f"❌ Error after {elapsed:.0f}ms: {e}")
        return {
            "query": query,
            "category": description,
            "found": 0,
            "time_ms": elapsed,
            "error": str(e),
            "success": False,
        }


async def run_complex_tests():
    """Run all complex query tests."""
    print("="*70)
    print("🔬 ROUND 2: COMPLEX QUERY TESTING")
    print("="*70)
    print(f"Testing {len(COMPLEX_QUERIES)} complex real-world queries\n")
    
    results = []
    for desc, query in COMPLEX_QUERIES:
        result = await test_complex_query(desc, query)
        results.append(result)
        await asyncio.sleep(2)  # Rate limiting
    
    return results


def analyze_complex_results(results: List[Dict]):
    """Deep analysis of complex query results."""
    print("\n" + "="*70)
    print("📊 DEEP ANALYSIS")
    print("="*70)
    
    # Success rate by category
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0, "found": 0}
        categories[cat]["total"] += 1
        if r["success"]:
            categories[cat]["success"] += 1
            categories[cat]["found"] += r["found"]
    
    print("\n📈 By Category:")
    for cat, stats in sorted(categories.items(), key=lambda x: x[1]["found"]/max(x[1]["total"], 1), reverse=True):
        avg = stats["found"] / max(stats["success"], 1)
        success_rate = (stats["success"] / stats["total"]) * 100
        print(f"   {cat:15s} | Success: {success_rate:5.1f}% | Avg posts: {avg:4.1f}")
    
    # Problematic queries (0-2 results)
    print("\n⚠️  LOW RESULTS (0-2 posts):")
    for r in results:
        if r["success"] and r["found"] <= 2:
            print(f"   • [{r['category']}] '{r['query'][:45]}...' - {r['found']} posts")
            print(f"     Targeted: {r.get('subreddits', [])}")
    
    # High performers
    print("\n🏆 HIGH PERFORMERS (10+ posts):")
    for r in results:
        if r["success"] and r["found"] >= 10:
            print(f"   • [{r['category']}] '{r['query'][:45]}...' - {r['found']} posts")
            print(f"     Distribution: {r.get('distribution', {})}")
    
    # Subreddit coverage
    print("\n🎯 Subreddit Coverage:")
    all_subreddits = {}
    for r in results:
        if r.get("distribution"):
            for sub, count in r["distribution"].items():
                all_subreddits[sub] = all_subreddits.get(sub, 0) + count
    
    top_subs = sorted(all_subreddits.items(), key=lambda x: x[1], reverse=True)[:10]
    for sub, count in top_subs:
        print(f"   r/{sub:20s} - {count} posts")
    
    # Timing analysis
    times = [r["time_ms"] for r in results if r["success"]]
    if times:
        print(f"\n⏱️  Timing:")
        print(f"   Average: {sum(times)/len(times):.0f}ms")
        print(f"   Min: {min(times):.0f}ms")
        print(f"   Max: {max(times):.0f}ms")


def generate_advanced_recommendations(results: List[Dict]):
    """Generate advanced optimization recommendations."""
    print("\n" + "="*70)
    print("💡 ADVANCED RECOMMENDATIONS (Round 2)")
    print("="*70)
    
    # Missing subreddits analysis
    print("\n1. MISSING SUBREDDIT MAPPINGS:")
    missing = [
        ("MCP", ["LocalLLaMA", "ClaudeAI", "MachineLearning"]),
        ("Cursor", ["CursorAI", "vscode", "LocalLLaMA"]),
        ("vLLM", ["LocalLLaMA", "MachineLearning"]),
        ("TGI", ["LocalLLaMA", "huggingface", "MachineLearning"]),
        ("systemd", ["linux", "selfhosted", "sysadmin"]),
        ("nginx", ["selfhosted", "homelab", "sysadmin"]),
        ("n8n", ["selfhosted", "automation", "n8n"]),
        ("nodered", ["homeautomation", "smarthome", "selfhosted"]),
        ("obsidian", ["ObsidianMD", "productivity", "selfhosted"]),
        ("nextcloud", ["NextCloud", "selfhosted", "privacy"]),
        ("MLX", ["LocalLLaMA", "apple", "MachineLearning"]),
        ("IPEX", ["IntelArc", "LocalLLaMA", "MachineLearning"]),
        ("gguf", ["LocalLLaMA"]),
        ("Q4_K_M", ["LocalLLaMA"]),
        ("speculative decoding", ["LocalLLaMA", "MachineLearning"]),
        ("prompt caching", ["LocalLLaMA", "OpenAI", "ClaudeAI"]),
        ("structured output", ["LocalLLaMA", "OpenAI", "ClaudeAI"]),
        ("CUDA OOM", ["LocalLLaMA", "nvidia", "MachineLearning"]),
        ("HIPAA", ["privacy", "selfhosted", "sysadmin"]),
        ("air gapped", ["privacy", "selfhosted", "sysadmin"]),
    ]
    
    for keyword, subs in missing:
        print(f"   '{keyword}' → {subs}")
    
    # Query optimization strategies
    print("\n2. QUERY OPTIMIZATION STRATEGIES:")
    strategies = [
        "Use 'selftext:' for error messages: selftext:'CUDA out of memory'",
        "Use 'title:' for specific tool names: title:ollama OR title:llama.cpp",
        "Combine with 'author:' for expert content: author:localhost",
        "Use 'url:' for GitHub discussions: url:github.com/ollama/ollama",
        "Filter by flair: flair:Discussion OR flair:Question",
    ]
    for s in strategies:
        print(f"   • {s}")
    
    # Reddit-specific tips
    print("\n3. REDDIT SEARCH ADVANCED TIPS:")
    tips = [
        "Reddit search ignores words <3 chars by default",
        "Use 'over18:no' to filter NSFW (useful for tech subreddits)",
        "Search within last month for recent issues: time_filter='month'",
        "Sort by 'comments' for discussion-heavy topics",
        "Cross-post detection: search same title across multiple subs",
    ]
    for t in tips:
        print(f"   • {t}")
    
    # Semantic search consideration
    print("\n4. SEMANTIC vs KEYWORD SEARCH:")
    print("   Current: Keyword-based with OR expansion")
    print("   Limitation: 'MCP' and 'Model Context Protocol' treated separately")
    print("   Idea: Use Gemini embeddings for semantic query understanding")
    print("   Idea: Cluster similar queries by intent")


def test_reddit_syntax_variations():
    """Test different Reddit search syntax variations."""
    print("\n" + "="*70)
    print("🧪 REDDIT SYNTAX VARIATIONS TEST")
    print("="*70)
    
    variations = [
        ("Basic", "llama.cpp ollama comparison"),
        ("Title only", "title:ollama AND title:performance"),
        ("Selftext", "selftext:quantized AND Q4_K_M"),
        ("OR operator", "ollama OR llama.cpp OR vLLM"),
        ("Exclude", "ollama -docker -kubernetes"),
        ("Combined", "title:LocalAI AND selftext:selfhosted"),
    ]
    
    for name, query in variations:
        expanded = expand_query(query)
        subreddits = get_target_subreddits(query)
        print(f"\n{name:12s}: {query[:40]}")
        print(f"             → Expanded: {expanded[:45]}...")
        print(f"             → Subreddits: {subreddits[:3]}...")


async def main():
    # Run complex tests
    results = await run_complex_tests()
    
    # Analyze
    analyze_complex_results(results)
    
    # Generate recommendations
    generate_advanced_recommendations(results)
    
    # Test syntax variations
    test_reddit_syntax_variations()
    
    # Summary
    print("\n" + "="*70)
    print("✅ ROUND 2 TESTING COMPLETE")
    print("="*70)
    
    successful = sum(1 for r in results if r["success"])
    total_found = sum(r["found"] for r in results if r["success"])
    avg_time = sum(r["time_ms"] for r in results) / len(results)
    
    print(f"\n📊 Summary:")
    print(f"   Queries tested: {len(results)}")
    print(f"   Successful: {successful}/{len(results)}")
    print(f"   Total posts found: {total_found}")
    print(f"   Average time: {avg_time:.0f}ms")
    print(f"   Average posts/query: {total_found/max(successful,1):.1f}")


if __name__ == "__main__":
    asyncio.run(main())
