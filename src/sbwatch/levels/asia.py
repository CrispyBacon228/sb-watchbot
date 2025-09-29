from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
import pytz
from sbwatch.util.dates import last_business_day

def asia_window_utc_for_last_bday(now: datetime, tz: str = "America/New_York"):
    """
    Asia session = 20:00–00:00 local, anchored to LAST BUSINESS DAY.
    e.g., if today is Monday, last business day is Friday, so use Fri 20:00–Sat 00:00 local.
    """
    z = pytz.timezone(tz)
    ref = last_business_day(now).astimezone(z)
    start_local = ref.replace(hour=20, minute=0, second=0, microsecond=0)
    end_local = start_local.replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def asia_high_low_from_df(df: pd.DataFrame, now: datetime, tz: str = "America/New_York"):
    """
    df must contain 'timestamp' (tz-aware UTC) and OHLC columns.
    """
    start_utc, end_utc = asia_window_utc_for_last_bday(now, tz)
    mask = (df["timestamp"] >= start_utc) & (df["timestamp"] < end_utc)
    if not mask.any():
        return None, None
    return float(df.loc[mask, "high"].max()), float(df.loc[mask, "low"].min())
