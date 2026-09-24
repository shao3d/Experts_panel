"""Date utility functions for the project."""

from datetime import datetime, timezone
import calendar


def get_cutoff_date(months: int = 3) -> datetime:
    """
    Calculate cutoff date N months ago from now (UTC).
    
    Handles month boundaries correctly:
    - March 31 - 3 months = Dec 31
    - May 31 - 3 months = Feb 28/29 (handles leap year)
    
    Args:
        months: Number of months to go back (default: 3)
        
    Returns:
        Naive datetime in UTC representing the cutoff date
        
    Note:
        Database uses naive UTC datetimes (datetime.utcnow),
        so this returns naive datetime for comparison.
    """
    now = datetime.utcnow()
    month = now.month - months
    year = now.year
    
    if month <= 0:
        month += 12
        year -= 1
    
    # Handle day overflow (e.g., March 31 - 3 months = Dec 31, not invalid)
    try:
        return now.replace(year=year, month=month)
    except ValueError:
        # Day doesn't exist in target month (e.g., May 31 -> Feb 30)
        last_day = calendar.monthrange(year, month)[1]
        return now.replace(year=year, month=month, day=last_day)


#: Canonical storage format for timestamp text columns (posts.created_at and
#: friends): naive UTC, space separator, seconds precision. Matches the
#: SQLAlchemy SQLite DATETIME rendering, so strings round-trip as real
#: datetimes and compare correctly in SQL.
CANONICAL_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_timestamp(value) -> datetime | None:
    """Parse stored timestamp text into a naive UTC datetime.

    Accepts the common shapes seen in the corpus and ingest artifacts:
    `YYYY-MM-DD` (date-only, means midnight), ISO with `T` or space separator,
    optional fractional seconds, optional trailing `Z` or UTC offset.

    Returns None for empty or unparsable values; callers decide whether that
    is "treat as old" (retrieval freshness) or a hard error (import).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def format_timestamp(value: datetime) -> str:
    """Render a datetime as the canonical timestamp string (drops microseconds)."""
    return value.strftime(CANONICAL_TIMESTAMP_FORMAT)


def to_canonical_timestamp(value, *, field: str = "timestamp") -> str | None:
    """Normalize any accepted timestamp shape to the canonical string.

    Returns None when the value is empty/missing. Raises ValueError when the
    value is present but unparsable — a wrong date silently stored would skew
    freshness ranking, so importers must fail loudly instead.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    parsed = parse_timestamp(value)
    if parsed is None:
        raise ValueError(
            f"{field}: cannot parse timestamp {value!r} "
            "(expected YYYY-MM-DD or ISO datetime like YYYY-MM-DDTHH:MM:SS)"
        )
    return format_timestamp(parsed)
