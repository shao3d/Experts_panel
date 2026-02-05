"""Reddit API client using asyncpraw (direct OAuth).

Direct Reddit API integration with asyncpraw.
Uses authenticated API for 60-100 req/min rate limit.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

import asyncpraw
from asyncpraw.models import Submission

logger = logging.getLogger(__name__)

# Smart subreddit targeting for better search results
# Maps topic keywords to relevant subreddits
SUBREDDIT_MAPPING = {
    # AI / LLM
    "llm": ["LocalLLaMA", "OpenAI", "ClaudeAI", "artificial", "MachineLearning"],
    "ai": ["artificial", "MachineLearning", "singularity", "OpenAI"],
    "local": ["LocalLLaMA", "selfhosted", "homelab"],
    "mcp": ["LocalLLaMA", "ClaudeAI", "MachineLearning", "artificial"],
    "cursor": ["CursorAI", "vscode", "LocalLLaMA", "artificial"],
    "cline": ["ClaudeAI", "vscode", "LocalLLaMA"],
    "vllm": ["LocalLLaMA", "MachineLearning", "artificial"],
    "tgi": ["LocalLLaMA", "huggingface", "MachineLearning"],
    "llamacpp": ["LocalLLaMA"],
    "llama.cpp": ["LocalLLaMA"],
    "gguf": ["LocalLLaMA"],
    "speculative decoding": ["LocalLLaMA", "MachineLearning"],
    "prompt caching": ["LocalLLaMA", "OpenAI", "ClaudeAI"],
    "structured output": ["LocalLLaMA", "OpenAI", "ClaudeAI", "MachineLearning"],
    "function calling": ["LocalLLaMA", "OpenAI", "ClaudeAI"],
    "mlx": ["LocalLLaMA", "apple", "MachineLearning"],
    "ipex": ["IntelArc", "LocalLLaMA", "MachineLearning"],
    
    # Voice / TTS / STT
    "tts": ["tts", "TextToSpeech", "LocalLLaMA", "selfhosted"],
    "stt": ["speechRecognition", "LocalLLaMA", "selfhosted"],
    "voice": ["speechRecognition", "tts", "LocalLLaMA", "selfhosted"],
    "speech": ["speechRecognition", "tts", "LocalLLaMA", "selfhosted"],
    "audio": ["audio", "voice", "musicproduction", "WeAreTheMusicMakers"],
    "whisper": ["LocalLLaMA", "speechRecognition", "selfhosted"],
    "kokoro": ["LocalLLaMA", "tts", "TextToSpeech"],
    
    # Programming
    "python": ["Python", "learnpython", "MachineLearning"],
    "javascript": ["javascript", "webdev", "reactjs"],
    "rust": ["rust", "learnrust", "Programming"],
    
    # Hardware
    "gpu": ["LocalLLaMA", "nvidia", "AMD", "hardware"],
    "nvidia": ["nvidia", "LocalLLaMA", "hardware"],
    "amd": ["AMD", "LocalLLaMA", "hardware"],
    "intel": ["IntelArc", "LocalLLaMA", "hardware"],
    "arc": ["IntelArc", "LocalLLaMA"],
    "rtx": ["nvidia", "LocalLLaMA", "hardware"],
    "mac": ["LocalLLaMA", "apple"],
    "apple silicon": ["LocalLLaMA", "apple", "MachineLearning"],
    "m1": ["LocalLLaMA", "apple"],
    "m2": ["LocalLLaMA", "apple"],
    "m3": ["LocalLLaMA", "apple"],
    "m4": ["LocalLLaMA", "apple"],
    "raspberry": ["LocalLLaMA", "raspberry_pi", "selfhosted"],
    
    # Tools / Software
    "docker": ["docker", "selfhosted", "homelab", "sysadmin"],
    "compose": ["docker", "selfhosted", "homelab"],
    "kubernetes": ["kubernetes", "selfhosted", "homelab", "sysadmin"],
    "k8s": ["kubernetes", "selfhosted", "homelab"],
    "ollama": ["LocalLLaMA", "ollama", "selfhosted"],
    "localai": ["LocalLLaMA", "selfhosted"],
    "home assistant": ["homeautomation", "smarthome", "selfhosted"],
    "automation": ["automation", "selfhosted", "homeautomation"],
    "n8n": ["n8n", "selfhosted", "automation"],
    "nodered": ["homeautomation", "smarthome", "selfhosted"],
    "homebridge": ["homeautomation", "smarthome", "selfhosted"],
    "nginx": ["selfhosted", "homelab", "sysadmin"],
    "systemd": ["linux", "selfhosted", "sysadmin"],
    "reverse proxy": ["selfhosted", "homelab", "sysadmin"],
    "obsidian": ["ObsidianMD", "productivity", "selfhosted"],
    "nextcloud": ["NextCloud", "selfhosted", "privacy"],
    
    # RAG / Vector DB
    "rag": ["LocalLLaMA", "MachineLearning", "artificial"],
    "vector": ["LocalLLaMA", "MachineLearning", "artificial"],
    "embedding": ["LocalLLaMA", "MachineLearning"],
    "database": ["LocalLLaMA", "database", "selfhosted"],
    "chromadb": ["LocalLLaMA", "selfhosted"],
    "qdrant": ["LocalLLaMA", "selfhosted"],
    
    # Privacy / Security
    "privacy": ["privacy", "selfhosted", "degoogle", "privacytoolsIO"],
    "security": ["privacy", "selfhosted", "sysadmin"],
    "offline": ["privacy", "selfhosted", "LocalLLaMA"],
    "air gapped": ["privacy", "selfhosted", "sysadmin"],
    "hipaa": ["privacy", "selfhosted", "sysadmin"],
    "compliance": ["privacy", "selfhosted"],
    "enterprise": ["LocalLLaMA", "selfhosted"],
    
    # Errors / Troubleshooting
    "cuda": ["LocalLLaMA", "nvidia", "MachineLearning"],
    "oom": ["LocalLLaMA", "nvidia", "MachineLearning"],
    "error": ["LocalLLaMA", "selfhosted"],
    "troubleshooting": ["LocalLLaMA", "selfhosted"],
    "fix": ["LocalLLaMA", "selfhosted"],
    "permission": ["linux", "selfhosted", "sysadmin"],
    "docker socket": ["docker", "selfhosted"],
    
    # Download / Setup
    "download": ["LocalLLaMA", "selfhosted"],
    "weights": ["LocalLLaMA"],
    "model": ["LocalLLaMA", "MachineLearning"],
    "quantized": ["LocalLLaMA"],
    "quantization": ["LocalLLaMA"],
    "q4": ["LocalLLaMA"],
    "q5": ["LocalLLaMA"],
    "q6": ["LocalLLaMA"],
    "q8": ["LocalLLaMA"],
    "fp16": ["LocalLLaMA"],
    
    # Default fallback
    "default": ["LocalLLaMA", "OpenAI", "artificial", "technology"],
}

# Query expansion for technical terms
# Expands abbreviations to improve search coverage
QUERY_EXPANSIONS = {
    "tts": ["text to speech", "TTS", "voice synthesis"],
    "stt": ["speech to text", "STT", "voice recognition", "speech recognition"],
    "llm": ["LLM", "language model", "AI model", "large language model"],
    "rag": ["RAG", "retrieval augmented generation", "vector search"],
    "mcp": ["MCP", "model context protocol"],
    "gpu": ["GPU", "graphics card", "video card"],
    "cpu": ["CPU", "processor"],
    "api": ["API", "application programming interface"],
    "ui": ["UI", "user interface"],
    "ux": ["UX", "user experience"],
    "db": ["database", "DB"],
    "docker": ["Docker", "containerization", "containers"],
    "kubernetes": ["Kubernetes", "k8s"],
    "selfhosted": ["selfhosted", "self-hosted", "homelab", "on-premise"],
    "open source": ["open source", "FOSS", "free software"],
    "mlx": ["MLX", "machine learning accelerators", "Apple Silicon ML"],
    "ipex": ["IPEX", "Intel Extension for PyTorch", "Intel GPU"],
    "gguf": ["GGUF", "Georgi Gerganov Universal Format", "llama.cpp format"],
    "q4": ["Q4", "4-bit quantization", "Q4_K_M"],
    "q5": ["Q5", "5-bit quantization", "Q5_K_M"],
    "speculative decoding": ["speculative decoding", "medusa decoding", "lookahead decoding"],
    "prompt caching": ["prompt caching", "context caching", "KV cache"],
    "structured output": ["structured output", "JSON mode", "function calling"],
    "cuda": ["CUDA", "NVIDIA GPU", "GPU acceleration"],
    "oom": ["OOM", "out of memory", "CUDA out of memory"],
    "hipaa": ["HIPAA", "healthcare compliance", "data privacy"],
    "json": ["JSON", "JavaScript Object Notation"],
    "yaml": ["YAML", "YAML Ain't Markup Language"],
}

def expand_query(query: str) -> str:
    """Expand technical abbreviations for better search coverage.
    
    Uses Reddit's OR operator to search for all variations.
    Example: "TTS engines" → '("text to speech" OR "TTS" OR "voice synthesis") engines'
    
    Respects Reddit search operators:
    - Excludes negative terms (-keyword) from expansion
    - Preserves title:, selftext:, author:, url: operators
    """
    import re
    
    # Extract negative terms (e.g., -docker, -kubernetes) to preserve them
    negative_terms = re.findall(r'(-\w+)', query)
    
    # Create a working copy without negative terms for expansion
    working_query = query
    for neg_term in negative_terms:
        working_query = working_query.replace(neg_term, "")
    
    query_lower = working_query.lower()
    expanded_terms = []
    
    for keyword, variations in QUERY_EXPANSIONS.items():
        # Skip if keyword is in negative terms
        if f"-{keyword}" in query.lower():
            continue
            
        # Use word boundary check for short terms (<=3 chars) to avoid partial matches
        if len(keyword) <= 3:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, working_query, re.IGNORECASE):
                or_group = " OR ".join([f'"{v}"' for v in variations])
                expanded_terms.append(f"({or_group})")
                working_query = re.sub(pattern, "", working_query, count=1, flags=re.IGNORECASE)
        elif keyword in query_lower:
            # Create OR group for this term
            or_group = " OR ".join([f'"{v}"' for v in variations])
            expanded_terms.append(f"({or_group})")
            # Remove original term (case-insensitive) to avoid duplication
            working_query = re.sub(re.escape(keyword), "", working_query, count=1, flags=re.IGNORECASE)
    
    if expanded_terms:
        # Combine expanded terms with remaining query and add back negative terms
        expanded_query = " ".join(expanded_terms) + " " + working_query.strip()
        if negative_terms:
            expanded_query += " " + " ".join(negative_terms)
        logger.info(f"Query expanded: '{query[:40]}...' → '{expanded_query[:60]}...'")
        return expanded_query.strip()
    
    return query


def get_target_subreddits(query: str) -> Optional[List[str]]:
    """Extract relevant subreddits based on query keywords.
    
    Args:
        query: User search query (English recommended)
        
    Returns:
        List of subreddit names or None for search all
    """
    query_lower = query.lower()
    matched_subreddits = set()
    
    # Check each keyword in mapping
    for keyword, subreddits in SUBREDDIT_MAPPING.items():
        if keyword in query_lower:
            matched_subreddits.update(subreddits)
    
    # Return matched subreddits or default if none matched
    if matched_subreddits:
        return list(matched_subreddits)[:5]  # Max 5 subreddits
    return SUBREDDIT_MAPPING["default"]


# Reddit API credentials (from Fly.io secrets)
REDDIT_CLIENT_ID = "-SPb2C1BNI82qJVWSej41Q"
REDDIT_CLIENT_SECRET = "ry0Pvmuf9fEC-vgu4XFh5tDE82ehnQ"
REDDIT_USERNAME = "External-Way5292"
REDDIT_PASSWORD = "3dredditforce"
REDDIT_USER_AGENT = "android:com.experts.panel:v1.0 (by /u/External-Way5292)"

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 50  # Conservative, below 60-100 limit


@dataclass
class RedditPost:
    """Reddit post data structure."""
    id: str
    title: str
    selftext: str
    score: int
    num_comments: int
    subreddit: str
    url: str
    permalink: str
    created_utc: float
    author: str


@dataclass
class RedditSearchResult:
    """Search result from Reddit."""
    posts: List[RedditPost]
    found_count: int
    query: str
    processing_time_ms: int


class RateLimiter:
    """Token bucket rate limiter for Reddit API calls."""
    
    def __init__(self, max_calls: int = MAX_REQUESTS_PER_MINUTE):
        self.max_calls = max_calls
        self.interval = 60.0 / max_calls
        self._lock = asyncio.Lock()
        self._last_call_time: Optional[datetime] = None
    
    async def acquire(self):
        """Wait if needed to respect rate limit."""
        async with self._lock:
            now = datetime.utcnow()
            if self._last_call_time is not None:
                elapsed = (now - self._last_call_time).total_seconds()
                if elapsed < self.interval:
                    wait_time = self.interval - elapsed
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            self._last_call_time = datetime.utcnow()


class RedditClient:
    """Async Reddit API client with OAuth."""
    
    def __init__(self):
        self.reddit: Optional[asyncpraw.Reddit] = None
        self.rate_limiter = RateLimiter()
        self._initialized = False
    
    async def initialize(self):
        """Initialize Reddit API connection."""
        if self._initialized:
            return
        
        try:
            self.reddit = asyncpraw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                username=REDDIT_USERNAME,
                password=REDDIT_PASSWORD,
                user_agent=REDDIT_USER_AGENT,
            )
            
            # Verify authentication
            user = await self.reddit.user.me()
            logger.info(f"Reddit API authenticated as: {user.name}")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            raise
    
    async def close(self):
        """Close Reddit API connection."""
        if self.reddit:
            await self.reddit.close()
            self._initialized = False
            logger.info("Reddit API connection closed")
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def search(
        self,
        query: str,
        subreddits: Optional[List[str]] = None,
        limit: int = 25,
        time_filter: str = "all",
        sort: str = "relevance"
    ) -> RedditSearchResult:
        """Search Reddit for posts matching query.
        
        Args:
            query: Search query (keywords)
            subreddits: List of subreddits to search (None = all)
            limit: Max number of posts to return (1-100)
            time_filter: Time filter for results (all, day, week, month, year)
            sort: Sort order (relevance, hot, top, new)
            
        Returns:
            RedditSearchResult with found posts (may be empty if no results)
            
        Raises:
            ValueError: If query is empty or invalid
            Exception: If Reddit API call fails
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        query = query.strip()
        limit = max(1, min(100, limit))  # Clamp between 1-100
        
        start_time = datetime.utcnow()
        
        if not self._initialized:
            await self.initialize()
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        try:
            posts = []
            
            # Build optimized query with OR operator for subreddits
            search_query = query
            
            if subreddits:
                # Filter and validate subreddits
                filtered_subreddits = [s.strip() for s in subreddits[:5] if s and s.strip()]
                
                if filtered_subreddits:
                    # Use Reddit's OR operator for efficient multi-subreddit search
                    # subreddit:foo OR subreddit:bar OR subreddit:baz
                    subreddit_filter = " OR ".join([f"subreddit:{s}" for s in filtered_subreddits])
                    search_query = f"{query} ({subreddit_filter})"
                    logger.info(f"OR search in: {filtered_subreddits}")
            
            # Single search call - more efficient than multiple subreddit searches
            await self.rate_limiter.acquire()
            subreddit = await self.reddit.subreddit("all")
            
            async for submission in subreddit.search(
                search_query,
                limit=limit,
                time_filter=time_filter,
                sort=sort
            ):
                posts.append(self._convert_submission(submission))
            
            # Remove duplicates by ID
            seen_ids = set()
            unique_posts = []
            for post in posts:
                if post.id not in seen_ids:
                    seen_ids.add(post.id)
                    unique_posts.append(post)
            
            # Sort by score
            unique_posts.sort(key=lambda p: p.score, reverse=True)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info(
                f"Reddit search: '{query[:50]}...' found {len(unique_posts)} unique posts "
                f"in {processing_time:.0f}ms"
            )
            
            return RedditSearchResult(
                posts=unique_posts[:limit],
                found_count=len(unique_posts),
                query=query,
                processing_time_ms=int(processing_time)
            )
            
        except Exception as e:
            logger.error(f"Reddit search failed for query '{query[:50]}...': {e}")
            raise
    
    def _convert_submission(self, submission: Submission) -> RedditPost:
        """Convert asyncpraw Submission to RedditPost."""
        # Safely extract subreddit name
        subreddit_name = "unknown"
        if submission.subreddit:
            try:
                subreddit_name = str(submission.subreddit)
            except Exception:
                pass
        
        # Safely extract author
        author_name = "[deleted]"
        if submission.author:
            try:
                author_name = str(submission.author)
            except Exception:
                pass
        
        return RedditPost(
            id=submission.id or "unknown",
            title=submission.title or "",
            selftext=submission.selftext or "",
            score=submission.score if submission.score is not None else 0,
            num_comments=submission.num_comments if submission.num_comments is not None else 0,
            subreddit=subreddit_name,
            url=submission.url or "",
            permalink=f"https://reddit.com{submission.permalink}" if submission.permalink and not submission.permalink.startswith('http') else submission.permalink or "",
            created_utc=submission.created_utc if submission.created_utc is not None else 0.0,
            author=author_name
        )


# Global client instance - initialized once and reused
_global_reddit_client: Optional[RedditClient] = None
_global_lock = asyncio.Lock()


async def get_global_reddit_client() -> RedditClient:
    """Get or create global RedditClient singleton.
    
    The client is initialized once and reused across requests.
    Must call close_global_reddit_client() on shutdown.
    """
    global _global_reddit_client
    async with _global_lock:
        if _global_reddit_client is None:
            _global_reddit_client = RedditClient()
            await _global_reddit_client.initialize()
        return _global_reddit_client


async def close_global_reddit_client():
    """Close global Reddit client. Call on application shutdown."""
    global _global_reddit_client
    async with _global_lock:
        if _global_reddit_client is not None:
            await _global_reddit_client.close()
            _global_reddit_client = None


async def search_reddit(
    query: str,
    subreddits: Optional[List[str]] = None,
    limit: int = 25,
    time_filter: str = "all",
    sort: str = "relevance",
    max_retries: int = 2,
    use_smart_targeting: bool = True
) -> RedditSearchResult:
    """Convenience function to search Reddit using global client.
    
    Args:
        query: Search query (non-empty string)
        subreddits: List of subreddits to search (optional)
        limit: Max results (1-100, default 25)
        time_filter: Time filter (all, day, week, month, year)
        sort: Sort order (relevance, hot, top, new)
        max_retries: Number of retries on transient errors (default 2)
        
    Returns:
        RedditSearchResult with posts (may be empty if no results found)
        
    Raises:
        ValueError: If query is empty or invalid
        Exception: If search fails after all retries or on auth errors
    """
    # Validate query early (don't retry on validation errors)
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")
    
    # Apply query expansion for technical terms
    expanded_query = expand_query(query)
    
    # Apply smart subreddit targeting if enabled and not explicitly provided
    if use_smart_targeting and subreddits is None:
        subreddits = get_target_subreddits(query)
        if subreddits:
            logger.info(f"Smart targeting: searching in subreddits: {subreddits}")
    
    # Adaptive sort strategy: use 'top' for quality-focused queries
    adaptive_sort = sort
    if sort == "relevance":
        quality_keywords = ['best', 'top', 'vs', 'comparison', 'alternative', 'recommended']
        if any(kw in query.lower() for kw in quality_keywords):
            adaptive_sort = "top"
            logger.info(f"Adaptive sort: switched to 'top' for quality query")
    
    last_error = None
    
    # Use expanded query for search
    query = expanded_query
    
    for attempt in range(max_retries + 1):
        try:
            client = await get_global_reddit_client()
            return await client.search(query, subreddits, limit, time_filter, adaptive_sort)
            
        except ValueError:
            # Don't retry validation errors
            raise
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Don't retry on auth errors
            if any(x in error_str for x in ['auth', 'unauthorized', 'forbidden', '401', '403']):
                logger.error(f"Reddit auth error, not retrying: {e}")
                raise
            
            # Don't retry on last attempt
            if attempt >= max_retries:
                break
            
            # Exponential backoff: 1s, 2s
            wait_time = 2 ** attempt
            logger.warning(f"Reddit search attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
            
            # Reset client on error to force reconnection
            try:
                await close_global_reddit_client()
            except Exception as close_err:
                logger.debug(f"Error closing Reddit client during retry: {close_err}")
    
    raise last_error
