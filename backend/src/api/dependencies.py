"""Shared API dependencies."""

import hashlib
import os
import secrets
import time

from fastapi import Header, HTTPException, status

from .. import config


_AGENT_CONTEXT_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


def verify_admin_secret(x_admin_secret: str = Header(default=None)) -> None:
    """Ensure the request carries the correct admin secret header."""
    admin_secret = os.getenv("ADMIN_SECRET")

    if not admin_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_SECRET is not configured",
        )

    if x_admin_secret != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret",
        )


def _check_agent_context_rate_limit(token: str) -> None:
    """Apply a simple in-process per-token rate limit for the MVP API."""
    limit = config.AGENT_CONTEXT_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Agent Context API rate limit exceeded",
        )

    now = time.monotonic()
    window_start = now - 60.0
    bucket_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    requests = [
        timestamp
        for timestamp in _AGENT_CONTEXT_RATE_LIMIT_BUCKETS.get(bucket_key, [])
        if timestamp >= window_start
    ]

    if len(requests) >= limit:
        _AGENT_CONTEXT_RATE_LIMIT_BUCKETS[bucket_key] = requests
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Agent Context API rate limit exceeded",
        )

    requests.append(now)
    _AGENT_CONTEXT_RATE_LIMIT_BUCKETS[bucket_key] = requests


def verify_agent_context_token(authorization: str = Header(default=None)) -> None:
    """Ensure the request carries the Agent Context API bearer token."""
    configured_token = config.AGENT_CONTEXT_API_TOKEN

    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AGENT_CONTEXT_API_TOKEN is not configured",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid agent context token",
        )

    supplied_token = authorization.removeprefix("Bearer ").strip()
    if not supplied_token or not secrets.compare_digest(supplied_token, configured_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid agent context token",
        )

    _check_agent_context_rate_limit(supplied_token)
