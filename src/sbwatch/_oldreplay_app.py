from __future__ import annotations
import os, json
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from databento import Historical

UTC = ZoneInfo("UTC")
ET  = ZoneInfo("America/New_York")

def _iso(dt: datetime) -> str:
    # Databento expects ISO8601 with timezone
    return dt.astimezone(UTC).isoformat()

def _fetch_hi_lo(start: datetime, end: datetime) -> tuple[float|None,float|None,int]:
    """Return (hi, lo, rows) for the given [start,end) UTC window."""
    h = Historical(os.getenv("DATABENTO_API_KEY"))  # key from .env
    store = h.timeseries.get_range(
        dataset=os.getenv("DB_DATASET", "GLBX.MDP3"),
        schema=os.getenv("DB_SCHEMA", "ohlcv-1m"),
        symbols=os.getenv("FRONT_SYMBOL", "NQU5"),
        start=_iso(start),
        end=_iso(end),
    )
    df = store.to_df()
    if df.empty:
        return None, None, 0
    return float(df["high"].max()), float(df["low"].min()), len(df)

def _prev_business_day(day_et: datetime) -> datetime:
    d = (day_et - timedelta(days=1)).date()
    # simple weekend adjust
    if d.weekday() == 6:  # Sun -> Fri
        d = d - timedelta(days=2)
    elif d.weekday() == 5:  # Sat -> Fri
        d = d - timedelta(days=1)
    return datetime.combine(d, datetime.min.time(), tzinfo=ET)

def build_levels(date: str, verbose: bool=False) -> dict:
    """Build Asia/London session highs/lows and PDH/PDL for the given YYYY-MM-DD (ET)."""
    if not os.getenv("DATABENTO_API_KEY"):
        raise RuntimeError("DATABENTO_API_KEY is not set")

    day_et = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=ET)

    # Session windows in UTC
    asia_start   = day_et.astimezone(UTC).replace(hour=0,  minute=0,  second=0, microsecond=0)
    asia_end     = day_et.astimezone(UTC).replace(hour=6,  minute=0,  second=0, microsecond=0)
    london_start = day_et.astimezone(UTC).replace(hour=8,  minute=0,  second=0, microsecond=0)
    london_end   = day_et.astimezone(UTC).replace(hour=12, minute=0,  second=0, microsecond=0)

    # Previous RTH (09:30–16:00 ET) -> 13:30–20:00 UTC during DST
    prev_et = _prev_business_day(day_et)
    rth_start = prev_et.replace(hour=9,  minute=30, second=0, microsecond=0).astimezone(UTC)
    rth_end   = prev_et.replace(hour=16, minute=0,  second=0, microsecond=0).astimezone(UTC)

    asia_hi,   asia_lo,   asia_rows   = _fetch_hi_lo(asia_start,   asia_end)
    london_hi, london_lo, london_rows = _fetch_hi_lo(london_start, london_end)
    pdh,       pdl,       rth_rows    = _fetch_hi_lo(rth_start,    rth_end)

    out = {
        "date": date,
        "pdh": pdh, "pdl": pdl,
        "asia_high": asia_hi, "asia_low": asia_lo,
        "london_high": london_hi, "london_low": london_lo,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/levels.json", "w") as f:
        json.dump(out, f)
    if verbose:
        print("[levels]", out)
        print("[rows] asia", asia_rows, "london", london_rows, "rth", rth_rows)
    return out

# --- ensure .env is loaded if present (so CLI sees env even when not exported) ---
from pathlib import Path
from dotenv import load_dotenv
env_path = (Path(__file__).resolve().parents[2] / ".env")
if env_path.exists():
    load_dotenv(env_path)
