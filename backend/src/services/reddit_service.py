"""Reddit Service - HTTP client for Reddit Proxy microservice.

This module provides async HTTP client to communicate with the Reddit Proxy
service running on Fly.io. Implements retry logic, circuit breaker pattern,
and type-safe response handling.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Configuration
REDDIT_PROXY_URL = "https://experts-reddit-proxy.fly.dev"
DEFAULT_TIMEOUT = 15.0  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0  # exponential backoff base


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RedditSource:
    """Single Reddit post source."""
    title: str
    url: str
    score: int
    comments_count: int
    subreddit: str


@dataclass
class RedditSearchResult:
    """Result from Reddit search."""
    markdown: str
    found_count: int
    sources: List[RedditSource]
    query: str
    processing_time_ms: int


@dataclass
class CircuitBreaker:
    """Circuit breaker for Reddit Proxy service."""
    failure_threshold: int = 5
    recovery_timeout: int = 30  # seconds
    
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: Optional[datetime] = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    
    async def call(self, func, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker: HALF_OPEN - testing service")
                else:
                    raise RedditServiceError(
                        "Circuit breaker is OPEN - Reddit service unavailable",
                        error_type="circuit_open"
                    )
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except RedditServiceError as e:
            # FIX: Don't count 4xx client errors as circuit breaker failures
            is_client_error = e.status_code is not None and 400 <= e.status_code < 500
            await self._on_failure(is_client_error=is_client_error)
            raise
        except Exception as e:
            await self._on_failure(is_client_error=False)
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker: CLOSED - service recovered")
            else:
                self._failure_count = 0
    
    async def _on_failure(self, is_client_error: bool = False):
        """Handle failed call.
        
        Args:
            is_client_error: If True, this is a 4xx client error - don't count toward circuit breaker.
        """
        async with self._lock:
            # FIX: Client errors (4xx) don't count toward circuit breaker
            if is_client_error:
                return
            
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()
            
            # FIX: In HALF_OPEN state, ANY failure immediately opens the circuit
            # In CLOSED state, need threshold failures to open
            if (self._state == CircuitState.HALF_OPEN or 
                self._failure_count >= self.failure_threshold):
                # FIX: Save previous state before changing for correct logging
                prev_state = self._state
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker: OPEN after {self._failure_count} failures "
                    f"(state was {prev_state.value})"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state


class RedditServiceError(Exception):
    """Custom exception for Reddit service errors."""
    
    def __init__(self, message: str, error_type: str = "unknown", status_code: Optional[int] = None):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


class RedditService:
    """Async HTTP client for Reddit Proxy microservice.
    
    Features:
    - Async HTTP requests with httpx
    - Exponential backoff retry (3 attempts)
    - Circuit breaker pattern for resilience
    - Type-safe response parsing
    - Comprehensive error handling
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
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        subreddits: Optional[List[str]] = None,
        sort: str = "relevance",
        time: str = "all"
    ) -> RedditSearchResult:
        """Search Reddit via Proxy Service.
        
        Args:
            query: Search query (1-500 chars)
            limit: Number of results (1-25, default 10)
            subreddits: Optional list of subreddits to search
            sort: Sort order (relevance, hot, new, top)
            time: Time filter (hour, day, week, month, year, all)
        
        Returns:
            RedditSearchResult with markdown and sources
        
        Raises:
            RedditServiceError: If request fails after retries
        """
        # Validate inputs
        if not query or len(query) > 500:
            raise ValueError("Query must be 1-500 characters")
        
        limit = max(1, min(25, limit))
        
        payload = {
            "query": query,
            "limit": limit,
            "sort": sort,
            "time": time
        }
        
        if subreddits:
            payload["subreddits"] = subreddits
        
        return await self._circuit_breaker.call(
            self._search_with_retry,
            payload
        )
    
    async def _search_with_retry(self, payload: Dict[str, Any]) -> RedditSearchResult:
        """Execute search with exponential backoff retry."""
        last_error: Optional[Exception] = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._execute_search(payload)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        f"Reddit search attempt {attempt} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Reddit search failed after {self.max_retries} attempts")
                    raise RedditServiceError(
                        f"Connection failed after {self.max_retries} attempts: {e}",
                        error_type="connection_error"
                    ) from e
            except httpx.HTTPStatusError as e:
                # Don't retry on 4xx errors (client errors)
                status_code = e.response.status_code
                if 400 <= status_code < 500:
                    raise RedditServiceError(
                        f"Client error {status_code}: {e.response.text}",
                        error_type="client_error",
                        status_code=status_code
                    ) from e
                # Retry on 5xx errors
                if attempt < self.max_retries:
                    wait_time = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        f"Reddit search attempt {attempt} failed with {status_code}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise RedditServiceError(
                        f"Server error after {self.max_retries} attempts: {status_code}",
                        error_type="server_error",
                        status_code=status_code
                    ) from e
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    wait_time = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        f"Reddit search attempt {attempt} failed unexpectedly: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise RedditServiceError(
                        f"Unexpected error after {self.max_retries} attempts: {e}",
                        error_type="unknown"
                    ) from e
        
        # Should not reach here, but just in case
        raise RedditServiceError(
            "All retry attempts exhausted",
            error_type="retry_exhausted"
        ) from last_error
    
    async def _execute_search(self, payload: Dict[str, Any]) -> RedditSearchResult:
        """Execute single search request."""
        client = await self._get_client()
        url = f"{self.base_url}/search"
        
        logger.debug(f"Reddit search request: {payload['query'][:50]}...")
        
        response = await client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse sources
        sources = [
            RedditSource(
                title=src.get("title", "Untitled"),
                url=src.get("url", ""),
                score=src.get("score", 0),
                comments_count=src.get("commentsCount", 0),
                subreddit=src.get("subreddit", "unknown")
            )
            for src in data.get("sources", [])
        ]
        
        result = RedditSearchResult(
            markdown=data.get("markdown", ""),
            found_count=data.get("foundCount", 0),
            sources=sources,
            query=data.get("query", payload["query"]),
            processing_time_ms=data.get("processingTimeMs", 0)
        )
        
        logger.info(
            f"Reddit search completed: {result.found_count} results "
            f"in {result.processing_time_ms}ms"
        )
        
        return result
    
    async def health_check(self) -> bool:
        """Check if Reddit Proxy service is healthy.
        
        Returns:
            True if service is healthy, False otherwise
        """
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
_reddit_service: Optional[RedditService] = None


def get_reddit_service() -> RedditService:
    """Get or create singleton RedditService instance."""
    global _reddit_service
    if _reddit_service is None:
        _reddit_service = RedditService()
    return _reddit_service


async def search_reddit(
    query: str,
    limit: int = 10,
    subreddits: Optional[List[str]] = None,
    sort: str = "relevance",
    time: str = "all"
) -> RedditSearchResult:
    """Convenience function to search Reddit.
    
    Args:
        query: Search query
        limit: Number of results
        subreddits: Optional subreddit filter
        sort: Sort order
        time: Time filter
    
    Returns:
        RedditSearchResult
    """
    service = get_reddit_service()
    return await service.search(query, limit, subreddits, sort, time)
