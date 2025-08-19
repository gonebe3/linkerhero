from __future__ import annotations

from datetime import datetime
import calendar


def next_month(dt: datetime) -> datetime:
    """Return dt advanced by one calendar month, clamping the day if needed."""
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


