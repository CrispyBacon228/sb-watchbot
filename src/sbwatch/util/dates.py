from __future__ import annotations
from datetime import datetime, timedelta
import pytz

def last_business_day(dt: datetime) -> datetime:
    """Return last business day (Mon–Fri). If Monday, returns prior Friday."""
    wd = dt.weekday()  # Mon=0..Sun=6
    delta = 1 if wd > 0 else 3
    return dt - timedelta(days=delta)

def in_session(dt: datetime, tz: str, start_h: int, end_h: int) -> bool:
    """Check if time in [start_h, end_h) local hour, handling midnight wrap."""
    z = pytz.timezone(tz)
    local = dt.astimezone(z)
    h = local.hour
    if start_h <= end_h:
        return start_h <= h < end_h
    # wraps midnight: e.g., 20–0
    return h >= start_h or h < end_h
