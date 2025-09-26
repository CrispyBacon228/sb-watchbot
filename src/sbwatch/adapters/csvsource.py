from __future__ import annotations
import csv
from datetime import datetime, timezone
from typing import Iterable

def iter_ohlcv_from_csv(path: str) -> Iterable[dict]:
    """
    Yield records with fields: time (UTC iso or epoch), open, high, low, close.
    CSV header must include: time,open,high,low,close
    """
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            t = row["time"]
            try:
                # iso8601
                dt = datetime.fromisoformat(t.replace("Z","+00:00")).astimezone(timezone.utc)
            except Exception:
                # epoch seconds
                dt = datetime.fromtimestamp(float(t), tz=timezone.utc)
            yield {
                "time": dt,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low":  float(row["low"]),
                "close":float(row["close"]),
            }
