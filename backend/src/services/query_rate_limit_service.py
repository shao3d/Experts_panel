"""Public query endpoint protection: per-IP rate limit + daily budget guard.

POST /api/v1/query is unauthenticated (the public Panel UI), so these guards
are the only protection for the OpenRouter budget. Both are in-process,
matching the Agent Context per-token limiter idiom in
``src/api/dependencies.py``: production runs a single uvicorn worker, so
in-memory state is sufficient. Counters reset on restart — this is an abuse
safety net, not a billing system.
"""

import ipaddress
import time
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from .. import config

_RATE_LIMIT_WINDOW_SECONDS = 3600.0
_MAX_TRACKED_IPS = 10_000

_PER_IP_BUCKETS: dict[str, list[float]] = {}
_DAILY_BUDGET_STATE: dict[str, object] = {"date": None, "count": 0}


def resolve_client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting.

    The backend sits behind Caddy in production, so the immediate peer is the
    proxy (loopback/private) and the real client is in X-Forwarded-For.
    X-Forwarded-For is trusted only from loopback/private peers: port 8000 is
    published, so a direct peer could otherwise spoof the header to rotate
    its rate-limit identity.
    """
    peer = request.client.host if request.client else "unknown"
    if _is_loopback_or_private(peer):
        forwarded = request.headers.get("x-forwarded-for", "")
        first_hop = forwarded.split(",")[0].strip() if forwarded else ""
        if first_hop:
            return first_hop
    return peer


def check_query_rate_limit(client_ip: str) -> None:
    """Enforce the per-IP sliding-window limit; raise 429 when exceeded."""
    if not config.QUERY_RATE_LIMIT_ENABLED:
        return

    limit = config.QUERY_RATE_LIMIT_PER_HOUR
    if limit <= 0:
        return

    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    timestamps = [
        timestamp
        for timestamp in _PER_IP_BUCKETS.get(client_ip, [])
        if timestamp >= window_start
    ]

    if len(timestamps) >= limit:
        _PER_IP_BUCKETS[client_ip] = timestamps
        retry_after = max(1, int(_RATE_LIMIT_WINDOW_SECONDS - (now - timestamps[0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many queries from this address. "
                f"Limit is {limit} per hour; try again later."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    timestamps.append(now)
    _PER_IP_BUCKETS[client_ip] = timestamps
    _prune_stale_buckets(now)


def check_and_consume_daily_budget() -> None:
    """Count one query against the global daily budget; raise 429 when empty."""
    limit = config.DAILY_QUERY_BUDGET
    if limit <= 0:
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _DAILY_BUDGET_STATE["date"] != today:
        _DAILY_BUDGET_STATE["date"] = today
        _DAILY_BUDGET_STATE["count"] = 0

    count = int(_DAILY_BUDGET_STATE["count"])  # type: ignore[assignment]
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Daily query budget is exhausted for today (UTC). "
                "Try again tomorrow."
            ),
            headers={"Retry-After": str(_seconds_until_utc_midnight())},
        )

    _DAILY_BUDGET_STATE["count"] = count + 1


def reset_rate_limit_state() -> None:
    """Clear in-memory guard state (tests and admin tooling only)."""
    _PER_IP_BUCKETS.clear()
    _DAILY_BUDGET_STATE["date"] = None
    _DAILY_BUDGET_STATE["count"] = 0


def _is_loopback_or_private(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return parsed.is_loopback or parsed.is_private


def _prune_stale_buckets(now: float) -> None:
    """Drop idle buckets so a large abusive IP pool cannot grow memory."""
    if len(_PER_IP_BUCKETS) <= _MAX_TRACKED_IPS:
        return
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    stale = [
        ip
        for ip, timestamps in _PER_IP_BUCKETS.items()
        if not timestamps or timestamps[-1] < window_start
    ]
    for ip in stale:
        del _PER_IP_BUCKETS[ip]


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    return max(1, 86400 - seconds_today)
