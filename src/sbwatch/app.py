from __future__ import annotations
import json, os
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

# --- Types ---
@dataclass
class DayLevels:
    date: str
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    london_high: Optional[float] = None
    london_low: Optional[float] = None

# --- Config ---
DATASET = os.getenv("DB_DATASET", "GLBX.MDP3")
SCHEMA = os.getenv("DB_SCHEMA", "ohlcv-1m")
SYMBOL = os.getenv("FRONT_SYMBOL", "NQZ5")

# London 02:00–05:00 ET => 06:00–09:00 UTC
ASIA_START_UTC, ASIA_END_UTC = 0, 6
LONDON_START_UTC, LONDON_END_UTC = 6, 9

DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
LEVELS_PATH = DATA_DIR / "levels.json"

# --- Helpers ---
def _parse_day_utc(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0
    )

def _utc_range(day: str, start_h: int, end_h: int):
    base = _parse_day_utc(day)
    return base.replace(hour=start_h), base.replace(hour=end_h)

def _is_weekend(dt_utc: datetime) -> bool:
    return dt_utc.weekday() >= 5  # Mon=0, Sun=6

def _prev_business_day_str(date_str: str) -> str:
    d = _parse_day_utc(date_str)
    d -= timedelta(days=1)
    while _is_weekend(d):
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")

def _fetch_hi_lo(day: str, start_h: int, end_h: int):
    """Fetch hi/lo in [start_h, end_h) UTC via Databento Historical (no divisor scaling)."""
    try:
        from databento import Historical
    except Exception as e:
        print("[error] Databento SDK not available:", e)
        return 0, None, None
    api_key = os.getenv("DATABENTO_API_KEY")
    if not api_key:
        print("[error] DATABENTO_API_KEY not set")
        return 0, None, None
    start, end = _utc_range(day, start_h, end_h)
    try:
        h = Historical(api_key)
        store = h.timeseries.get_range(
            dataset=DATASET, schema=SCHEMA, symbols=SYMBOL,
            start=start.isoformat(), end=end.isoformat(),
        )
        df = store.to_df()
    except Exception as e:
        print(f"[error] Databento query failed ({start} -> {end}):", e)
        return 0, None, None
    if len(df) == 0:
        return 0, None, None
    return len(df), float(df["high"].max()), float(df["low"].min())

# --- Public API ---
def build_levels(date: str, verbose: bool = False) -> DayLevels:
    prev_bd = _prev_business_day_str(date)
    pdh_rows, pdh, _ = _fetch_hi_lo(prev_bd, 13, 20)
    _, _, pdl = _fetch_hi_lo(prev_bd, 13, 20)
    asia_rows, asia_hi, asia_lo = _fetch_hi_lo(date, ASIA_START_UTC, ASIA_END_UTC)
    lon_rows, lon_hi, lon_lo = _fetch_hi_lo(date, LONDON_START_UTC, LONDON_END_UTC)

    levels = DayLevels(
        date=date, pdh=pdh, pdl=pdl,
        asia_high=asia_hi, asia_low=asia_lo,
        london_high=lon_hi, london_low=lon_lo,
    )
    if verbose:
        print(f"[rows] pdh/pdl={pdh_rows} asia={asia_rows} london={lon_rows}")
        print("[levels]", asdict(levels))
    LEVELS_PATH.write_text(json.dumps(asdict(levels)))
    return levels

def load_levels_json() -> DayLevels | None:
    if not LEVELS_PATH.exists():
        return None
    try:
        return DayLevels(**json.loads(LEVELS_PATH.read_text()))
    except Exception as e:
        print("[warn] failed to load levels.json:", e)
        return None

def run_live(*a, **k): raise NotImplementedError
def run_replay(*a, **k): raise NotImplementedError
__all__ = ["DayLevels", "build_levels", "load_levels_json", "run_live", "run_replay"]
