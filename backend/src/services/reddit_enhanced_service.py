"""Enhanced Reddit Service with deep content analysis.

This module provides advanced Reddit aggregation strategies:
1. Parallel searches with different parameters (relevance, hot, new, top)
2. Multi-subreddit targeting for tech/business queries
3. Deep content fetching via get_post_details
4. Comment analysis for top posts
"""

import asyncio
import logging
import re
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from datetime import datetime

import httpx

from .. import config
from .reddit_service import RedditServiceError, CircuitBreaker
from .google_ai_studio_client import create_google_ai_studio_client

logger = logging.getLogger(__name__)

# Configuration
REDDIT_PROXY_URL = "https://experts-reddit-proxy.fly.dev"
DEFAULT_TIMEOUT = 30.0  # HTTP timeout - enough for cold start (~15s) + search
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0

# Model for Subreddit Scouting
# Using Gemini 3 Flash Preview as requested for high intelligence
MODEL_SCOUT = "gemini-3-flash-preview"

# Tech-related subreddits for targeted searches
TECH_SUBREDDITS = [
    "programming",
    "MachineLearning",
    "artificial",
    "LocalLLaMA",
    "ChatGPT",
    "claudeAI",
    "OpenAI",
    "Anthropic",
    "technology",
    "webdev",
    "python",
    "rust",
    "javascript",
    "startups",
    "Entrepreneur",
    "SaaS",
    "indiehackers",
]

# Query Expansions for Technical Terms
# Maps short acronyms to broader search terms including synonyms and related concepts
QUERY_EXPANSIONS = {
    "llm": ['"Large Language Model"', "LLM", "GPT", "Claude", "Llama", "Mistral", "LocalLLaMA", "GGUF", "quantization"],
    "rag": ["RAG", '"Retrieval Augmented Generation"', '"vector database"', "embeddings", "GraphRAG"],
    "tts": ["TTS", '"text to speech"', '"voice synthesis"', "ElevenLabs", "Kokoro"],
    "stt": ["STT", '"speech to text"', '"voice recognition"', "Whisper", "transcription"],
    "mcp": ["MCP", '"Model Context Protocol"', "server"],
    "gpu": ["GPU", "NVIDIA", "CUDA", "VRAM", "hardware", "3090", "4090"],
    "docker": ["Docker", "container", "kubernetes", "k8s", "compose"],
    "python": ["Python", "pip", "PyPI", "script", "asyncio"],
    "rust": ["Rust", "Rustlang", "cargo", "crate"],
    "react": ["React", "ReactJS", "NextJS", "frontend"],
    "arch": ["architecture", "design", "pattern", "trade-off", "latency", "throughput", "production"],
    "biz": ["cost", "pricing", "billing", "margin", "COGS", "economics"],
}

# Pre-compile expansion logic for performance
# 1. Build map: 'llm' -> '(Large Language Model OR LLM ...)'
_EXPANSION_MAP = {k.lower(): f"({' OR '.join(v)})" for k, v in QUERY_EXPANSIONS.items()}

# 2. Build regex pattern once: \b(llm|rag|...)\b
_EXPANSION_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _EXPANSION_MAP.keys()) + r')\b',
    re.IGNORECASE
)

# Constants
MAX_TARGET_SUBREDDITS = 7

# High-Signal Markers for "Title-Only" Strategy
# Used to find structured guides, tutorials, and deep dives
HIGH_SIGNAL_MARKERS = [
    '"Guide"', '"Tutorial"', '"Deep Dive"', '"Analysis"', 
    '"Benchmark"', '"Cheat Sheet"', '"Roadmap"', '"How to"',
    '"Post-Mortem"', '"Lessons Learned"'
]

# Conflict/Solution Markers for "Discussion" Strategy
# Used to find comparisons and solved problems
COMPARISON_MARKERS = [
    "vs", "versus", "comparison", "alternative", 
    "solved", "solution", "fixed", "workaround",
    "switched to", "migrated from", "failed", "regret"
]

# General popular subreddits
POPULAR_SUBREDDITS = [
    "AskReddit",
    "explainlikeimfive",
    "NoStupidQuestions",
    "LifeProTips",
    "personalfinance",
    "investing",
]


@dataclass
class RedditPost:
    """Enhanced Reddit post with full content."""
    id: str
    title: str
    url: str
    permalink: str
    score: int
    num_comments: int
    subreddit: str
    author: str
    created_utc: int
    selftext: str = ""
    is_self: bool = False
    # Enriched data
    full_content: Optional[str] = None
    top_comments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EnhancedSearchResult:
    """Result from enhanced Reddit search."""
    posts: List[RedditPost]
    total_found: int
    query: str
    strategies_used: List[str]
    processing_time_ms: int


class RedditEnhancedService:
    """Enhanced Reddit service with parallel searches and deep analysis.
    
    Features:
    - Parallel searches with different sort parameters
    - Multi-subreddit targeting
    - Deep content fetching for top posts
    - Comment analysis
    - Deduplication across sources
    """
    
    def __init__(
        self,
        base_url: str = REDDIT_PROXY_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._circuit_breaker = CircuitBreaker()
        self._client: Optional[httpx.AsyncClient] = None
        self._llm_client = create_google_ai_studio_client()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _expand_query(self, query: str) -> str:
        """Expand query with technical synonyms to improve recall.
        
        Uses pre-compiled single-pass regex replacement.
        Example: "best LLM" -> "best (LLM OR "Large Language Model" OR GPT ...)"
        """
        # Avoid double expansion if query already contains OR/AND
        if " OR " in query or " AND " in query:
            return query
            
        def replace_callback(match):
            word = match.group(0).lower()
            return _EXPANSION_MAP.get(word, match.group(0))

        # Perform single-pass substitution using global pre-compiled pattern
        return _EXPANSION_PATTERN.sub(replace_callback, query)
    
    async def _scout_subreddits(self, query: str) -> List[str]:
        """Use Gemini 3 Flash to detect relevant subreddits dynamically.
        
        This acts as an intelligent 'Navigator', mapping user intent to specific
        Reddit communities, handling Russian queries, and prioritizing technical sources.
        """
        try:
            prompt = f"""You are an expert Reddit OSINT Navigator.
User Query: "{query}"

Task: Identify the top 3-7 most relevant *technical* subreddits for this query.
Rules:
1. If the query is in Russian, translate intent to English to find global communities.
2. Prioritize specific technical communities (e.g., 'LocalLLaMA' over 'technology', 'rust' over 'programming').
3. Include niche communities if the topic is specific (e.g., 'selfhosted', 'dataengineering').
4. Return ONLY a raw JSON array of strings. No Markdown. No Explanations.

Example Output: ["LocalLLaMA", "MachineLearning", "Ollama"]
"""
            # Use Gemini 3 Flash Preview for high-intelligence scouting
            response = await self._llm_client.chat_completions_create(
                model=MODEL_SCOUT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # Deterministic
            )
            
            content = response.choices[0].message.content.strip()
            
            # Robust JSON extraction: Find first '[' and last ']'
            try:
                start_idx = content.find('[')
                end_idx = content.rfind(']')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]
                    subreddits = json.loads(json_str)
                else:
                    logger.warning(f"Gemini Scout returned no JSON array: {content[:100]}...")
                    return []
            except json.JSONDecodeError as e:
                logger.warning(f"Gemini Scout JSON parse error: {e}. Content: {content[:100]}...")
                return []
            
            # Validation and Sanitization
            valid_subs = []
            if isinstance(subreddits, list):
                for s in subreddits:
                    if isinstance(s, str) and len(s) > 1:
                        # Clean up 'r/' prefix if present
                        clean_name = s.strip().replace('r/', '').replace('/r/', '')
                        # Reddit names are alphanumeric + underscore
                        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', clean_name)
                        if clean_name:
                            valid_subs.append(clean_name)
            
            if valid_subs:
                logger.info(f"🤖 Gemini Scout found targets for '{query}': {valid_subs}")
                return valid_subs
            
            return []
            
        except Exception as e:
            logger.warning(f"Gemini Scout failed: {e}. Falling back to global search.")
            return []
    
    async def search_enhanced(
        self,
        query: str,
        target_posts: int = 25,
        include_comments: bool = True,
        subreddits: Optional[List[str]] = None
    ) -> EnhancedSearchResult:
        """Execute enhanced Reddit search with multiple strategies.
        
        Args:
            query: Search query
            target_posts: Target number of unique posts to return
            include_comments: Whether to fetch top comments for best posts
            subreddits: Optional list of specific subreddits to search
        
        Returns:
            EnhancedSearchResult with posts from multiple search strategies
        """
        start_time = datetime.utcnow()
        strategies_used = []
        all_posts: Dict[str, RedditPost] = {}  # id -> post for deduplication
        
        # 1. Expand Query (Smart Query Expansion)
        # "best LLM" -> "best (LLM OR GPT OR Claude...)"
        original_query = query
        expanded_query = self._expand_query(query)
        if expanded_query != original_query:
            logger.info(f"Expanded query: '{original_query}' -> '{expanded_query}'")
        
        # 2. Dynamic Scouting (AI-Powered)
        if subreddits is None:
            # Use Gemini 3 Flash to find targets
            subreddits = await self._scout_subreddits(query)
        
        sort_tasks = []
        
        # 3. Strategy Selection
        if subreddits:
            # OPTION A: Targeted Search via OR Operator (Optimization #1)
            # Instead of N requests for N subreddits, we make parallel requests 
            # with different SORTS on the COMBINED set of subreddits.
            # Query: "(expanded_query) AND (subreddit:A OR subreddit:B ...)"
            
            logger.info(f"Targeted search active ({len(subreddits)} subs) - Using Combined OR Strategy")
            
            # Construct subreddit filter: (subreddit:A OR subreddit:B)
            # Limit number of subreddits to prevent extremely long URLs
            target_subs = [s.strip() for s in subreddits[:MAX_TARGET_SUBREDDITS] if s.strip()]
            
            if target_subs:
                # Use quotes for safety, though typically not needed for strict alphanumeric names
                subreddit_filter = " OR ".join([f"subreddit:{s}" for s in target_subs])
                
                # Combine logic: (Query) AND (Subreddits)
                final_query = f"({expanded_query}) AND ({subreddit_filter})"
                
                # Run parallel sorts on this combined scope
                # "relevance": Best match overall
                # "top": Highest quality/engagement (year)
                # "new": Freshness check (month)
                
                # Task 1: Relevance (All time)
                sort_tasks.append((
                    "combined_relevance", 
                    self._search_with_sort(final_query, sort="relevance", limit=25, time="all")
                ))
                
                # Task 2: Top (Past Year) - High quality signal
                sort_tasks.append((
                    "combined_top_year", 
                    self._search_with_sort(final_query, sort="top", limit=25, time="year")
                ))
                
                # Task 3: New (Past Month) - Freshness signal
                sort_tasks.append((
                    "combined_new_month", 
                    self._search_with_sort(final_query, sort="new", limit=25, time="month")
                ))
                
                # OPTION C: High-Signal Strategies (Additive Improvements)
                # These run in PARALLEL with the above to catch specific high-value post types
                
                # Task 4: "Sniper" Strategy - High Signal Guides (Title Only)
                # Finds: "Ultimate Guide to LLMs", "RAG Deep Dive"
                high_signal_or = " OR ".join(HIGH_SIGNAL_MARKERS)
                # Note: We use expanded_query to catch specific tool names in titles (e.g. "Llama 3 Guide" for "LLM")
                # Logic: title:(expanded_query) AND title:(Guide OR Tutorial...)
                title_query = f"title:({expanded_query}) AND title:({high_signal_or})"
                if subreddits:
                     # Add subreddit filter if we have targets
                    title_query = f"({title_query}) AND ({subreddit_filter})"
                
                sort_tasks.append((
                    "high_signal_title",
                    self._search_with_sort(title_query, sort="relevance", limit=15, time="all")
                ))

                # Task 5: "Conflict & Solution" Strategy
                # Finds: "Claude vs GPT", "Solved: Docker error", "Alternative to X"
                comparison_or = " OR ".join(COMPARISON_MARKERS)
                # Logic: (expanded_query) AND (vs OR comparison OR solved...)
                comparison_query = f"({expanded_query}) AND ({comparison_or})"
                if subreddits:
                    comparison_query = f"({comparison_query}) AND ({subreddit_filter})"

                sort_tasks.append((
                    "comparison_heavy",
                    self._search_with_sort(comparison_query, sort="relevance", limit=15, time="all")
                ))

            else:
                # Fallback if sanitization removed all subs (unlikely)
                logger.warning("All subreddits filtered out, falling back to global")
                sort_tasks.append((
                    "global_relevance", 
                    self._search_with_sort(expanded_query, sort="relevance", limit=25, time="all")
                ))
                
        else:
            # OPTION B: Global Search (No specific topic detected)
            logger.info("No specific topic detected - Enabling global search")
            
            # Task 1: Global Relevance
            sort_tasks.append((
                "global_relevance", 
                self._search_with_sort(expanded_query, sort="relevance", limit=25, time="all")
            ))
            
            # Task 2: Global Hot (Trending)
            sort_tasks.append((
                "global_hot", 
                self._search_with_sort(expanded_query, sort="hot", limit=25, time="month")
            ))
            
            # Task 3: Global High Signal (Additive)
            # Try to find guides even in global search
            high_signal_or = " OR ".join(HIGH_SIGNAL_MARKERS)
            title_query = f"title:({expanded_query}) AND title:({high_signal_or})"
            sort_tasks.append((
                "global_high_signal",
                self._search_with_sort(title_query, sort="relevance", limit=15, time="all")
            ))

            # Task 4: Global Conflict & Solution (Additive)
            # Try to find comparisons/solutions even in global search
            comparison_or = " OR ".join(COMPARISON_MARKERS)
            comparison_query = f"({expanded_query}) AND ({comparison_or})"
            sort_tasks.append((
                "global_comparison_heavy",
                self._search_with_sort(comparison_query, sort="relevance", limit=15, time="all")
            ))
        results = await asyncio.gather(
            *[task for _, task in sort_tasks],
            return_exceptions=True
        )
        
        for (strategy_name, _), result in zip(sort_tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"Strategy {strategy_name} failed: {result}")
                continue
            
            strategies_used.append(strategy_name)
            for post in result:
                if post.id not in all_posts:
                    all_posts[post.id] = post
                else:
                    # Merge scores if post found via multiple strategies
                    existing = all_posts[post.id]
                    existing.score = max(existing.score, post.score)
                    existing.num_comments = max(existing.num_comments, post.num_comments)
        
        logger.info(f"🔍 REDDIT SEARCH: query='{query[:50]}...' | strategies={strategies_used} | unique_posts={len(all_posts)}")
        
        # Fallback: if no posts found with specific strategies, try broader search without expansion/filters
        if len(all_posts) == 0 and len(strategies_used) > 0:
            logger.warning("No posts found, trying fallback broader search...")
            try:
                # Try simple query (no expansion), global, top/year
                fallback_posts = await self._search_with_sort(original_query, sort="top", limit=25, time="year")
                for post in fallback_posts:
                    if post.id not in all_posts:
                        all_posts[post.id] = post
                if fallback_posts:
                    strategies_used.append("fallback_top_year")
                    logger.info(f"Fallback search found {len(fallback_posts)} posts")
            except Exception as e:
                logger.error(f"Fallback search also failed: {e}")
        
        # Sort by combined engagement score with Time Decay
        # Algorithm: (Score) / (Time + 2)^1.5
        # This boosts fresh content (2025/2026) over ancient high-score posts
        current_time = datetime.utcnow().timestamp()
        
        def calculate_freshness_score(p: RedditPost) -> float:
            # Base engagement
            base_score = p.score + (p.num_comments * 2)
            
            # If no date, treat as moderately old (neutral decay) to be safe
            if not p.created_utc:
                return base_score
                
            # Calculate age in hours
            age_seconds = max(0, current_time - p.created_utc)
            age_hours = age_seconds / 3600
            
            # Gravity decay (Hacker News style)
            # Fresh posts (0-24h) get almost full score. 
            # 1 year old posts get heavy penalty.
            gravity = 1.5
            return base_score / pow((age_hours + 2), gravity)

        sorted_posts = sorted(
            all_posts.values(),
            key=calculate_freshness_score,
            reverse=True
        )
        
        # Take top posts for deep analysis
        top_posts = sorted_posts[:target_posts]
        
        # Deep content fetching for top posts (if enabled)
        if include_comments and top_posts:
            logger.info(f"Fetching deep content for top {len(top_posts)} posts...")
            deep_tasks = [
                self._enrich_post_content(post)
                for post in top_posts[:10]  # Limit deep analysis to top 10
            ]
            enriched = await asyncio.gather(*deep_tasks, return_exceptions=True)
            
            for i, result in enumerate(enriched):
                if isinstance(result, Exception):
                    logger.warning(f"Failed to enrich post {top_posts[i].id}: {result}")
                else:
                    top_posts[i] = result
        
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return EnhancedSearchResult(
            posts=top_posts,
            total_found=len(all_posts),
            query=query,
            strategies_used=strategies_used,
            processing_time_ms=processing_time_ms
        )
    
    async def _search_with_sort(
        self,
        query: str,
        sort: str = "relevance",
        limit: int = 25,
        time: str = "all"
    ) -> List[RedditPost]:
        """Search Reddit with specific sort parameter."""
        payload = {
            "query": query,
            "limit": min(limit, 25),
            "sort": sort,
            "time": time
        }
        
        return await self._circuit_breaker.call(
            self._execute_search,
            payload
        )
    
    async def _search_subreddit(
        self,
        query: str,
        subreddit: str,
        limit: int = 25
    ) -> List[RedditPost]:
        """Search within a specific subreddit."""
        payload = {
            "query": query,
            "limit": min(limit, 25),
            "sort": "relevance",
            "time": "all",
            "subreddits": [subreddit]
        }
        
        return await self._circuit_breaker.call(
            self._execute_search,
            payload
        )
    
    async def _execute_search(self, payload: Dict[str, Any]) -> List[RedditPost]:
        """Execute search request and parse results."""
        client = await self._get_client()
        url = f"{self.base_url}/search"
        
        logger.debug(f"Reddit search: {payload}")
        
        response = await client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # DEBUG: Check what we got from proxy
        sources = data.get("sources", [])
        logger.info(f"REDDIT PROXY DEBUG: Got {len(sources)} sources")
        if sources:
            first = sources[0]
            has_selftext = bool(first.get("selftext"))
            logger.info(f"REDDIT PROXY DEBUG: First source has selftext: {has_selftext}, keys: {list(first.keys())}")
        
        posts = []
        for src in data.get("sources", []):
            url = src.get("url", "")
            # Extract post ID from Reddit URL safely
            # Reddit URL format: .../comments/{post_id}/{slug}/ or .../comments/{post_id}/
            post_id = ""
            if "/" in url:
                parts = [p for p in url.split("/") if p]
                # Find 'comments' segment and take the next part as post_id
                if "comments" in parts:
                    idx = parts.index("comments")
                    if idx + 1 < len(parts):
                        post_id = parts[idx + 1]
                # Fallback: if no comments segment, use last non-empty part
                elif len(parts) >= 1:
                    post_id = parts[-1]
            
            # Try to parse creation date
            created_utc = src.get("created_utc") or src.get("created") or 0
            
            post = RedditPost(
                id=post_id or "unknown",
                title=src.get("title") or "Untitled",
                url=url,
                permalink=url,
                score=src.get("score") or 0,
                num_comments=src.get("commentsCount") or 0,
                subreddit=src.get("subreddit") or "unknown",
                author=src.get("author") or "unknown",
                created_utc=created_utc,
                selftext=src.get("selftext") or "",  # CRITICAL: Get content from proxy
                top_comments=src.get("top_comments") or [] # NEW: Get comments from proxy
            )
            posts.append(post)
        
        return posts
    
    async def _enrich_post_content(self, post: RedditPost) -> RedditPost:
        """Fetch full content and comments for a post.
        
        Note: This would require the reddit-proxy to expose get_post_details
        and get_comments tools. For now, it's a placeholder for future enhancement.
        """
        # TODO: Implement when reddit-proxy supports get_post_details
        # This would make MCP calls to fetch:
        # - Full selftext (not truncated)
        # - Top comments with content
        return post
    
    async def health_check(self) -> bool:
        """Check if Reddit Proxy service is healthy."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Reddit Proxy health check failed: {e}")
            return False


# Singleton instance
_enhanced_service: Optional[RedditEnhancedService] = None


def get_reddit_enhanced_service() -> RedditEnhancedService:
    """Get or create singleton RedditEnhancedService instance."""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = RedditEnhancedService()
    return _enhanced_service


async def search_reddit_enhanced(
    query: str,
    target_posts: int = 25,
    include_comments: bool = True,
    subreddits: Optional[List[str]] = None
) -> EnhancedSearchResult:
    """Convenience function for enhanced Reddit search.
    
    Args:
        query: Search query
        target_posts: Target number of unique posts
        include_comments: Whether to fetch comments for top posts
        subreddits: Optional list of subreddits to search
    
    Returns:
        EnhancedSearchResult
    """
    service = get_reddit_enhanced_service()
    return await service.search_enhanced(
        query=query,
        target_posts=target_posts,
        include_comments=include_comments,
        subreddits=subreddits
    )



