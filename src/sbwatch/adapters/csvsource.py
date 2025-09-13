from __future__ import annotations
import os, csv
from typing import Iterable, Dict, Any, List

def find_csv_for_date(date: str) -> str | None:
    candidates: List[str] = [
        f"data/{date}.csv",
        f"data/NQ-{date}-1m.csv",
        f"data/{date}-1m.csv",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def iter_bars_csv(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                "ts": row["ts"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            }
