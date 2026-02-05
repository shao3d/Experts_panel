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
            
            # Filter and validate subreddits
            filtered_subreddits = []
            if subreddits:
                filtered_subreddits = [s.strip().lower() for s in subreddits[:3] if s and s.strip()]
            
            if filtered_subreddits:
                # Search in specific subreddits (max 3)
                per_subreddit_limit = max(1, limit // len(filtered_subreddits))
                
                for subreddit_name in filtered_subreddits:
                    await self.rate_limiter.acquire()
                    try:
                        subreddit = await self.reddit.subreddit(subreddit_name)
                        
                        async for submission in subreddit.search(
                            query,
                            limit=per_subreddit_limit,
                            time_filter=time_filter,
                            sort=sort
                        ):
                            posts.append(self._convert_submission(submission))
                    except Exception as e:
                        logger.warning(f"Failed to search r/{subreddit_name}: {e}")
                        # Continue with other subreddits
            else:
                # Search all of Reddit
                await self.rate_limiter.acquire()
                async for submission in self.reddit.subreddit("all").search(
                    query,
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
            permalink=f"https://reddit.com{submission.permalink}" if submission.permalink else "",
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
    max_retries: int = 2
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
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            client = await get_global_reddit_client()
            return await client.search(query, subreddits, limit, time_filter, sort)
            
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
