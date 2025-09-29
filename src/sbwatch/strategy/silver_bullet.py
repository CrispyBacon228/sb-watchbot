from __future__ import annotations
from datetime import datetime
import pytz
import pandas as pd
from typing import Optional, Tuple
from sbwatch.levels.asia import asia_high_low_from_df

NY = pytz.timezone("America/New_York")

def in_ny_killzone_10_11(dt: datetime) -> bool:
    local = dt.astimezone(NY)
    return local.hour == 10  # [10:00, 11:00)

def detect_signal(df: pd.DataFrame, now: datetime, tz: str = "America/New_York") -> Optional[Tuple[str, float]]:
    """
    Return ("LONG", price) or ("SHORT", price) if Asia H/L is broken during 10–11 NY.
    Simple but robust: ensures live pipeline can generate real alerts when data is flowing.
    """
    ah, al = asia_high_low_from_df(df, now, tz=tz)
    if ah is None or al is None:
        return None
    last = df.iloc[-1]
    price = float(last["close"])
    if not in_ny_killzone_10_11(now):
        return None
    if price > ah:
        return ("LONG", price)
    if price < al:
        return ("SHORT", price)
    return None
