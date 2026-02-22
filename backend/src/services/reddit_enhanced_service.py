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
DEFAULT_TIMEOUT = 60.0  # HTTP timeout - enough for Fly.io cold start (~30-45s) + search
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
    is_technical_guide: bool = False
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
    
    async def _plan_search_strategy(self, query: str) -> Dict[str, Any]:
        """Use Gemini 3 Flash to create a search plan (Subreddits + Intent-based Queries).
        
        Returns:
            Dict with keys:
            - 'subreddits': List[str]
            - 'queries': List[str]
            - 'keywords': List[str]
            - 'time_filter': str ('month' | 'year' | 'all')
            - 'intent': str ('how_to' | 'comparison' | 'troubleshooting' | 'news' | 'discussion')
        """
        try:
            prompt = f"""You are an expert Reddit OSINT Navigator.
User Query: "{query}"

Task: Create a precise Search Plan.
1. Identify 3-7 relevant technical subreddits.
2. Generate 3-5 SPECIFIC search queries.
3. Extract 2-3 CRITICAL keywords.
4. Assess Temporal Context:
   - Is this a fast-moving topic (AI, News, Bugs)? -> "month" or "year"
   - Is this evergreen (Concepts, Algorithms)? -> "all"
5. Classify Intent: how_to, comparison, troubleshooting, news, discussion.

Output JSON structure:
{{
  "subreddits": ["LocalLLaMA", "ClaudeAI"],
  "queries": ["Claude Code workflow", "Claude setup"],
  "keywords": ["Skills", "CLI"],
  "time_filter": "month",
  "intent": "how_to"
}}
"""
            # Use Gemini 3 Flash Preview for high-intelligence scouting
            response = await self._llm_client.chat_completions_create(
                model=MODEL_SCOUT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # Deterministic
            )
            
            content = response.choices[0].message.content.strip()
            
            # Robust JSON extraction
            try:
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]
                    plan = json.loads(json_str)
                else:
                    logger.warning(f"Gemini Scout returned no JSON object: {content[:100]}...")
                    return {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}
            except json.JSONDecodeError as e:
                logger.warning(f"Gemini Scout JSON parse error: {e}. Content: {content[:100]}...")
                return {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}
            
            # Validation and Sanitization
            valid_subs = []
            raw_subs = plan.get("subreddits", [])
            if isinstance(raw_subs, list):
                for s in raw_subs:
                    if isinstance(s, str) and len(s) > 1:
                        # Clean up 'r/' prefix if present
                        clean_name = s.strip().replace('r/', '').replace('/r/', '')
                        # Reddit names are alphanumeric + underscore
                        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', clean_name)
                        if clean_name:
                            valid_subs.append(clean_name)
            
            valid_queries = []
            raw_queries = plan.get("queries", [])
            if isinstance(raw_queries, list):
                valid_queries = [q for q in raw_queries if isinstance(q, str) and len(q) > 3]

            valid_keywords = []
            raw_keywords = plan.get("keywords", [])
            if isinstance(raw_keywords, list):
                valid_keywords = [k for k in raw_keywords if isinstance(k, str) and len(k) > 2]
                
            time_filter = plan.get("time_filter", "all")
            if time_filter not in ["hour", "day", "week", "month", "year", "all"]:
                time_filter = "all"
                
            intent = plan.get("intent", "discussion")

            result = {
                "subreddits": valid_subs, 
                "queries": valid_queries, 
                "keywords": valid_keywords,
                "time_filter": time_filter,
                "intent": intent
            }
            
            if valid_subs or valid_queries:
                logger.info(f"🤖 Gemini Scout Plan for '{query}': {result}")
            
            return result
            
        except Exception as e:
            logger.warning(f"Gemini Scout failed: {e}. Falling back to global search.")
            return {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}
    
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
        search_plan = {"subreddits": [], "queries": [], "keywords": [], "time_filter": "all", "intent": "discussion"}
        if subreddits is None:
            # Use Gemini 3 Flash to find targets and generate intent queries
            search_plan = await self._plan_search_strategy(query)
            subreddits = search_plan.get("subreddits", [])
        
        target_keywords = search_plan.get("keywords", [])
        scout_time_filter = search_plan.get("time_filter", "all")
        
        sort_tasks = []
        
        # 3. Strategy Selection
        if subreddits:
            # OPTION A: Targeted Search via OR Operator (Optimization #1)
            # Instead of N requests for N subreddits, we make parallel requests 
            # with different SORTS on the COMBINED set of subreddits.
            # Query: "(expanded_query) AND (subreddit:A OR subreddit:B ...)"
            
            logger.info(f"Targeted search active ({len(subreddits)} subs) - Using Combined OR Strategy. Time Filter: {scout_time_filter}")
            
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
                
                # Task 1: Relevance (Context Aware Time)
                sort_tasks.append((
                    "combined_relevance", 
                    self._search_with_sort(final_query, sort="relevance", limit=25, time=scout_time_filter)
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
                
                # Task 4: AI Intent Queries (NEW)
                # Use specific queries generated by Gemini 3 Scout
                ai_queries = search_plan.get("queries", [])
                if ai_queries:
                    logger.info(f"🤖 Adding AI Intent Queries: {ai_queries}")
                    for i, ai_q in enumerate(ai_queries[:3]): # Limit to top 3 to prevent rate limits
                        # Combine AI query with subreddit filter
                        full_ai_q = f"({ai_q}) AND ({subreddit_filter})"
                        sort_tasks.append((
                            f"ai_intent_{i}",
                            self._search_with_sort(full_ai_q, sort="relevance", limit=20, time=scout_time_filter)
                        ))

                # Task 5: "Sniper" Strategy - High Signal Guides (Title Only)
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
                    self._search_with_sort(title_query, sort="relevance", limit=15, time=scout_time_filter)
                ))

                # Task 6: "Conflict & Solution" Strategy
                # Finds: "Claude vs GPT", "Solved: Docker error", "Alternative to X"
                comparison_or = " OR ".join(COMPARISON_MARKERS)
                # Logic: (expanded_query) AND (vs OR comparison OR solved...)
                comparison_query = f"({expanded_query}) AND ({comparison_or})"
                if subreddits:
                    comparison_query = f"({comparison_query}) AND ({subreddit_filter})"

                sort_tasks.append((
                    "comparison_heavy",
                    self._search_with_sort(comparison_query, sort="relevance", limit=15, time=scout_time_filter)
                ))

                # Task 7: "Timeless Classics" Strategy (New in R3)
                # Finds: "Best practices", "Bible", "Handbook" - highly upvoted content from ANY time
                # Logic: (expanded_query) AND (best practice OR bible OR handbook)
                classic_markers = " OR ".join(['"Best practices"', '"Bible"', '"Handbook"', '"Cheatsheet"', '"Gold standard"'])
                classic_query = f"({expanded_query}) AND ({classic_markers})"
                if subreddits:
                    classic_query = f"({classic_query}) AND ({subreddit_filter})"
                
                # Timeless always uses "all"
                sort_tasks.append((
                    "timeless_classic",
                    self._search_with_sort(classic_query, sort="top", limit=10, time="all")
                ))

            else:
                # Fallback if sanitization removed all subs (unlikely)
                logger.warning("All subreddits filtered out, falling back to global")
                sort_tasks.append((
                    "global_relevance", 
                    self._search_with_sort(expanded_query, sort="relevance", limit=25, time=scout_time_filter)
                ))
                
        else:
            # OPTION B: Global Search (No specific topic detected)
            logger.info(f"No specific topic detected - Enabling global search. Time Filter: {scout_time_filter}")
            
            # Task 1: Global Relevance
            sort_tasks.append((
                "global_relevance", 
                self._search_with_sort(expanded_query, sort="relevance", limit=25, time=scout_time_filter)
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
                self._search_with_sort(title_query, sort="relevance", limit=15, time=scout_time_filter)
            ))

            # Task 4: Global Conflict & Solution (Additive)
            # Try to find comparisons/solutions even in global search
            comparison_or = " OR ".join(COMPARISON_MARKERS)
            comparison_query = f"({expanded_query}) AND ({comparison_or})"
            sort_tasks.append((
                "global_comparison_heavy",
                self._search_with_sort(comparison_query, sort="relevance", limit=15, time=scout_time_filter)
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
            
            # Determine if this strategy yields "technical guides" (evergreen content)
            is_technical = (
                strategy_name.startswith("ai_intent_") or 
                strategy_name == "high_signal_title" or
                strategy_name == "code_hunter"
            )
            
            for post in result:
                if post.id not in all_posts:
                    if is_technical:
                        post.is_technical_guide = True
                    # Track which strategy found this post (keep the first one if multiple find it)
                    if not hasattr(post, "found_by_strategy"):
                         post.found_by_strategy = strategy_name
                    all_posts[post.id] = post
                else:
                    # Merge scores if post found via multiple strategies
                    existing = all_posts[post.id]
                    existing.score = max(existing.score, post.score)
                    existing.num_comments = max(existing.num_comments, post.num_comments)
                    # If ANY strategy found it as technical, mark it so
                    if is_technical:
                        existing.is_technical_guide = True
                    # If existing didn't have strategy tracked, add it (shouldn't happen given logic above)
                    if not hasattr(existing, "found_by_strategy"):
                         existing.found_by_strategy = strategy_name
        
        logger.info(f"🔍 REDDIT SEARCH: query='{query[:50]}...' | strategies={strategies_used} | unique_posts={len(all_posts)}")
        
        # Fallback: if no posts found with specific strategies, try broader search without expansion/filters
        if len(all_posts) == 0 and len(strategies_used) > 0:
            logger.warning("No posts found, trying fallback broader search...")
            try:
                # Try simple query (no expansion), global, top/year
                fallback_posts = await self._search_with_sort(original_query, sort="top", limit=25, time="year")
                for post in fallback_posts:
                    if post.id not in all_posts:
                        post.found_by_strategy = "fallback"
                        all_posts[post.id] = post
                if fallback_posts:
                    strategies_used.append("fallback_top_year")
                    logger.info(f"Fallback search found {len(fallback_posts)} posts")
            except Exception as e:
                logger.error(f"Fallback search also failed: {e}")
        
        # --- PHASE 2: DEDUPLICATION & CLEANUP ---
        unique_posts = self._deduplicate_posts(list(all_posts.values()))
        logger.info(f"Deduplication: {len(all_posts)} -> {len(unique_posts)} unique posts")

        # --- PHASE 3: AI RERANKING (The Brain) ---
        # Instead of relying solely on mathematical formula, we use Gemini 3 Flash
        # to assess semantic relevance.
        
        # 1. Pre-sort by heuristic to send only promising candidates to LLM (save tokens)
        # Sort by combined engagement score with Time Decay
        # Algorithm: (Score) / (Time + 2)^1.5
        current_time = datetime.utcnow().timestamp()
        
        def calculate_freshness_score(p: RedditPost) -> float:
            # Base engagement
            base_score = p.score + (p.num_comments * 2)
            
            # Boost Factors
            boost = 1.0
            
            # 1. Technical Guide Boost (Context-Aware)
            if p.is_technical_guide:
                boost *= 1.2
            
            # 2. Semantic Keyword Boost
            if target_keywords:
                title_lower = p.title.lower()
                matches = sum(1 for k in target_keywords if k.lower() in title_lower)
                if matches > 0:
                    keyword_boost = min(1.0 + (matches * 0.5), 3.0)
                    boost *= keyword_boost
            
            score = base_score * boost
            
            is_highly_relevant = p.is_technical_guide or (boost > 1.5)
            if is_highly_relevant:
                return score
            
            # Gravity Decay
            if not p.created_utc:
                return score
                
            age_seconds = max(0, current_time - p.created_utc)
            age_hours = age_seconds / 3600
            gravity = 1.5
            return score / pow((age_hours + 2), gravity)

        heuristic_sorted = sorted(
            unique_posts,
            key=calculate_freshness_score,
            reverse=True
        )

        # 2. AI Reranking (Top 40 candidates)
        # We assume top 40 heuristic posts contain the best answer.
        CANDIDATES_FOR_RERANK = 40
        candidates = heuristic_sorted[:CANDIDATES_FOR_RERANK]
        others = heuristic_sorted[CANDIDATES_FOR_RERANK:]
        
        # Only run AI rerank if we have enough candidates
        if candidates:
            try:
                reranked_candidates = await self._ai_rerank_posts(query, candidates)
                # Combine: AI reranked (high confidence) + others (low confidence fallback)
                final_sorted = reranked_candidates + others
            except Exception as e:
                logger.error(f"AI Reranking failed: {e}. Falling back to heuristic sort.")
                final_sorted = heuristic_sorted
        else:
            final_sorted = heuristic_sorted
        
        # Take top posts for deep analysis
        top_posts = final_sorted[:target_posts]
        
        # Deep content fetching for top posts (if enabled)
        if include_comments and top_posts:
            logger.info(f"Fetching deep content for top {len(top_posts)} posts...")
            deep_tasks = [
                self._enrich_post_content(post)
                for post in top_posts[:15]  # Limit deep analysis to top 15
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
            total_found=len(unique_posts),
            query=query,
            strategies_used=strategies_used,
            processing_time_ms=processing_time_ms
        )

    def _deduplicate_posts(self, posts: List[RedditPost]) -> List[RedditPost]:
        """Deduplicate posts based on URL and fuzzy title match."""
        unique = []
        seen_urls = set()
        seen_titles = set()
        
        # Helper to normalize URL (remove query params, trailing slash)
        def normalize_url(url: str) -> str:
            if not url: return ""
            u = url.split('?')[0].rstrip('/')
            return u
            
        # Helper to normalize title (simple alphanum sort)
        def normalize_title(title: str) -> str:
            # "How to fix X?" -> "howtofixx"
            return re.sub(r'[^a-z0-9]', '', title.lower())

        for post in posts:
            norm_url = normalize_url(post.url)
            norm_title = normalize_title(post.title)
            
            # Check URL exact match
            if norm_url in seen_urls:
                continue
                
            # Check Title exact match (simple dedup)
            # This handles cross-posts effectively enough for MVP
            if norm_title in seen_titles:
                continue
                
            seen_urls.add(norm_url)
            seen_titles.add(norm_title)
            unique.append(post)
            
        return unique

    async def _ai_rerank_posts(self, query: str, posts: List[RedditPost]) -> List[RedditPost]:
        """Rerank posts using Gemini 3 Flash based on semantic relevance."""
        if not posts:
            return []
            
        logger.info(f"🧠 AI Reranking {len(posts)} posts for query: '{query}'")
        
        # Prepare batch prompt
        posts_context = []
        for i, p in enumerate(posts):
            # Limit content to save tokens, title is most important for filtering
            preview = (p.selftext or "")[:300].replace("\n", " ")
            posts_context.append(f"ID: {i} | Title: {p.title} | Sub: {p.subreddit} | Preview: {preview}")
            
        context_str = "\n".join(posts_context)
        
        prompt = f"""You are a Relevance Ranking Engine.
Query: "{query}"

Task: Rate the relevance of the following Reddit posts to the query on a scale of 0.0 to 1.0.
- 1.0: Perfect answer, technical guide, solution, or highly relevant discussion.
- 0.0: Spam, joke, completely unrelated, or question without answers.

Posts:
{context_str}

Output JSON format ONLY:
{{
  "ratings": [
    {{"id": 0, "score": 0.95, "reason": "Exact guide"}},
    {{"id": 1, "score": 0.1, "reason": "Joke thread"}}
  ]
}}
"""
        try:
            # Use MODEL_SYNTHESIS (Gemini 3 Flash Preview) for intelligence
            response = await self._llm_client.chat_completions_create(
                model=config.MODEL_SYNTHESIS, 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            try:
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    data = json.loads(content[start_idx:end_idx+1])
                    # Robust parsing: handle string IDs from LLM
                    ratings = {}
                    for r in data.get('ratings', []):
                        try:
                            r_id = int(r.get('id'))
                            ratings[r_id] = r
                        except (ValueError, TypeError):
                            continue
                else:
                    ratings = {}
            except Exception:
                logger.warning("Failed to parse reranking JSON")
                ratings = {}
                
            # Assign scores and sort
            # We combine AI score with original engagement signal for robustness
            scored_posts = []
            for i, post in enumerate(posts):
                rating = ratings.get(i)
                ai_score = rating['score'] if rating else 0.5 # Default neutral
                
                # Formula: 70% AI Relevance + 30% Normalized Engagement
                # This ensures highly relevant but low-upvote posts (niche answers) win,
                # but absolute trash with high AI score (hallucination guard) is kept in check slightly,
                # and massive viral posts (high engagement) get a small boost if relevance is okay.
                
                # Normalize engagement (log scale roughly)
                engagement = post.score + post.num_comments
                norm_engagement = min(engagement / 1000.0, 1.0) # Cap at 1000 points
                
                final_score = (ai_score * 0.8) + (norm_engagement * 0.2)
                
                # Store AI reasoning for debugging/logging
                if rating and 'reason' in rating:
                    # You could attach this to post if you want to show it in UI later
                    pass
                    
                scored_posts.append((post, final_score))
            
            # Sort desc
            scored_posts.sort(key=lambda x: x[1], reverse=True)
            
            # Return just posts
            return [p for p, _ in scored_posts]
            
        except Exception as e:
            logger.error(f"Error in _ai_rerank_posts: {e}")
            return posts # Fallback to original order
    
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
        """Fetch full content and comments for a post via Proxy /details endpoint."""
        try:
            client = await self._get_client()
            url = f"{self.base_url}/details"
            
            payload = {
                "postId": post.id,
                "subreddit": post.subreddit,
                "comment_limit": 100,  # CRITICAL: Get more comments for "30% more meat"
                "comment_depth": 5     # CRITICAL: Go deeper into threads
            }
            
            # Using circuit breaker logic for robustness, though individual failures shouldn't stop the pipeline
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # Enriched data from proxy
                # Proxy returns sanitized 'selftext' which we treat as full_content
                full_text = data.get("selftext") or data.get("body") or ""
                post.full_content = full_text
                post.top_comments = data.get("top_comments") or []
                
                # Update basic fields if better data available
                # If original selftext was truncated or missing, update it
                if full_text and len(full_text) > len(post.selftext):
                     post.selftext = full_text

                logger.info(f"✅ Enriched post {post.id} (r/{post.subreddit}): {len(post.top_comments)} comments")
            else:
                logger.warning(f"Failed to enrich post {post.id}: Status {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Error enriching post {post.id}: {e}")
            
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



