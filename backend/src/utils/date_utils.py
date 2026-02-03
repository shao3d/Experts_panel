"""Date utility functions for the project."""

from datetime import datetime
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
