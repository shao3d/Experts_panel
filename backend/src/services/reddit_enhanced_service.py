"""Enhanced Reddit Service with deep content analysis.

This module provides advanced Reddit aggregation strategies:
1. Parallel searches with different parameters (relevance, hot, new, top)
2. Multi-subreddit targeting for tech/business queries
3. Deep content fetching via get_post_details
4. Comment analysis for top posts
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from datetime import datetime

import httpx

from .reddit_service import RedditServiceError, CircuitBreaker

logger = logging.getLogger(__name__)

# Configuration
REDDIT_PROXY_URL = "https://experts-reddit-proxy.fly.dev"
DEFAULT_TIMEOUT = 30.0  # HTTP timeout - enough for cold start (~15s) + search
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0

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
        
        # Strategy 1: General search with different sort parameters
        sort_tasks = []
        for sort in ["relevance", "hot", "top"]:
            task = self._search_with_sort(query, sort=sort, limit=25, time="all")
            sort_tasks.append((f"search_{sort}", task))
        
        # Strategy 2: Search in specific subreddits (Now enabled)
        if subreddits:
            for subreddit in subreddits[:3]:
                task = self._search_subreddit(query, subreddit, limit=25)
                sort_tasks.append((f"subreddit_{subreddit}", task))
        
        # Strategy 3: Fallback general search (DISABLED for AI queries to prevent noise)
        # Only use this if NO specific strategies were used (i.e., no topic detected)
        if not strategies_used:
             task = self._search_with_sort(query, sort="hot", limit=25, time="year")
             sort_tasks.append(("search_hot_year", task))
        
        # Execute all searches in parallel with error isolation
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
        
        logger.info(f"🔍 REDDIT SEARCH: query='{query[:50]}...' | strategies={len(strategies_used)} | unique_posts={len(all_posts)} | strategies_used={strategies_used}")
        
        # Fallback: if no posts found with specific strategies, try broader search
        if len(all_posts) == 0 and len(strategies_used) > 0:
            logger.warning("No posts found with specific strategies, trying broader search...")
            try:
                # Try without subreddit restrictions, last year, sorted by top
                fallback_posts = await self._search_with_sort(query, sort="top", limit=25, time="year")
                for post in fallback_posts:
                    if post.id not in all_posts:
                        all_posts[post.id] = post
                if fallback_posts:
                    strategies_used.append("fallback_top_year")
                    logger.info(f"Fallback search found {len(fallback_posts)} posts")
            except Exception as e:
                logger.error(f"Fallback search also failed: {e}")
        
        # Sort by combined engagement score (upvotes + comments*2)
        sorted_posts = sorted(
            all_posts.values(),
            key=lambda p: p.score + p.num_comments * 2,
            reverse=True
        )
        
        # Take top posts for deep analysis
        top_posts = sorted_posts[:target_posts]
        
        # Strategy 3: Deep content fetching for top posts (if enabled)
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
            
            post = RedditPost(
                id=post_id or "unknown",
                title=src.get("title") or "Untitled",
                url=url,
                permalink=url,
                score=src.get("score") or 0,
                num_comments=src.get("commentsCount") or 0,
                subreddit=src.get("subreddit") or "unknown",
                author="unknown",
                created_utc=0,
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


# Subreddit recommendations by topic
SUBREDDIT_BY_TOPIC = {
    "ai": [
        "MachineLearning", "artificial", "LocalLLaMA", "ChatGPT", "claudeAI", "OpenAI",
        "singularity", "Futurology", "technology", "learnmachinelearning", "deeplearning", "CSCareerQuestions", "AskEngineers"
    ],
    "llm": [
        "LocalLLaMA", "ChatGPT", "claudeAI", "OpenAI", "Anthropic", "ollama", 
        "textgenerationwebui", "SillyTavernAI", "aiwars"
    ],
    "programming": ["programming", "webdev", "python", "rust", "javascript", "coding", "developer", "coding"],
    "startup": ["startups", "Entrepreneur", "SaaS", "indiehackers", "smallbusiness", "sideproject"],
    "business": ["business", "Entrepreneur", "marketing", "sales", "agency", "consulting"],
    "product_management": ["ProductManagement", "softwareengineering", "agile", "scrum", "projectmanagement", "devops"],
    "productivity": ["productivity", "LifeProTips", "selfimprovement", "getdisciplined", "Notion", "obsidianmd"],
    "general": ["AskReddit", "explainlikeimfive", "NoStupidQuestions"],
}


def get_recommended_subreddits(query: str) -> List[str]:
    """Get recommended subreddits based on query keywords.
    
    Supports both English and Russian queries. Falls back to tech subreddits
    if no specific topic detected.
    
    Args:
        query: User query
    
    Returns:
        List of recommended subreddit names
    """
    query_lower = query.lower()
    recommended: Set[str] = set()
    topic_found = False
    
    # Check each topic for keyword matches (English + Russian)
    topic_keywords = {
        "ai": [
            # English
            "ai", "artificial intelligence", "machine learning", "ml", "model", "gpt", "claude", "llm", "neural", "architecture", "architect", "engineer", "learn", "understand", "system",
            "hallucination", "rag", "retrieval", "embedding", "vector", "context", "token", "fine-tuning", "training", "inference",
            # Russian
            "ии", "искусственный интеллект", "машинное обучение", "модель", "агент", "нейросеть", "чатбот",
            "нейронная сеть", "языковая модель", "большая модель", "искусственный", "интеллект", "архитектура", "разбираться", "понимать", "учиться", "система",
            "галлюцинаци", "rag", "рэг", "эмбеддинг", "вектор", "контекст", "токен", "файн-тюнинг", "обучение", "инференс"
        ],
        "llm": [
            # English
            "llm", "large language model", "gpt", "claude", "openai", "anthropic", "mistral", "llama", "prompt", "prompting", "jailbreak",
            # Russian
            "большая языковая модель", "гпт", "клод", "опенаи", "anthropic", "mistral", "llama",
            "llm", "языковая модель", "трансформер", "промпт", "промт", "джейлбрейк"
        ],
        "programming": [
            # English
            "code", "programming", "developer", "software", "app", "web", "python", "javascript", "rust", "engineer", "build", "design", "tech",
            # Russian
            "код", "программирование", "разработчик", "софт", "приложение", "веб", "пайтон", "жаваскрипт",
            "rust", "rustlang", "golang", "typescript", "разрабатывать", "разработка", "инженер", "строить", "дизайн"
        ],
        "product_management": [
            # English
            "spec", "specification", "requirements", "prd", "jira", "confluence", "linear", "agile", "scrum", "product manager", "project",
            # Russian
            "спецификация", "тз", "техническое задание", "требования", "jira", "confluence", "linear", "эджайл", "скрам", "продукт", "проект", "документация"
        ],
        "startup": [
            # English
            "startup", "founder", "entrepreneur", "business idea", "mvp", "funding", "vc",
            # Russian
            "стартап", "основатель", "предприниматель", "бизнес идея", "фандинг", "венчур",
            "инвестиции", "бизнес", "запуск", "мвп"
        ],
        "business": [
            # English
            "business", "marketing", "sales", "revenue", "customer", "product",
            # Russian
            "бизнес", "маркетинг", "продажи", "выручка", "клиент", "продукт", "монетизация"
        ],
        "productivity": [
            # English
            "productivity", "habit", "routine", "focus", "procrastination", "time management",
            # Russian
            "продуктивность", "привычка", "рутина", "фокус", "прокрастинация", "тайм-менеджмент",
            "организация", "эффективность"
        ],
    }
    
    for topic, keywords in topic_keywords.items():
        if any(kw in query_lower for kw in keywords):
            recommended.update(SUBREDDIT_BY_TOPIC.get(topic, []))
            topic_found = True
    
    # If no specific topic detected, include tech subreddits as fallback
    if not topic_found:
        recommended.update(["technology", "Futurology", "singularity"])
        # Only add general noise if NO topic is found
        recommended.update(SUBREDDIT_BY_TOPIC["general"])
    
    return list(recommended)[:5]  # Return top 5 matches
