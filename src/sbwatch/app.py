
import os, json


def _get_databento_hist():
    """
    Construct a Databento Historical client in a way that works across SDK versions.
    Tries positional key first; falls back to env-based construction.
    """
    import os
    try:
        from databento import Historical
    except Exception as e:
        raise RuntimeError(f"[databento] Could not import Historical: {e}")

    key = os.getenv("DATABENTO_API_KEY", "").strip()

    # Try positional (most versions accept this).
    if key:
        try:
            return Historical(key)
        except TypeError:
            # Fallback: rely on env only.
            os.environ["DATABENTO_API_KEY"] = key

    # Try no-arg (env based).
    try:
        return Historical()
    except Exception as e:
        raise RuntimeError(f"[databento] Could not create Historical client: {e}")



def _make_db_client():
    import os
    try:
        from databento import Historical
    except Exception as e:
        raise RuntimeError(f"[databento] Could not import Historical: {e}")

    key = os.getenv("DATABENTO_API_KEY", "").strip()
    if not key:
        # Many SDK versions will read the env internally; still warn if empty.
        try:
            return Historical()  # env-based
        except TypeError:
            raise RuntimeError("[databento] DATABENTO_API_KEY is not set")

    # Try positional first (newer/most versions)
    try:
        return Historical(key)
    except TypeError:
        # Fallback to env-based construction
        os.environ["DATABENTO_API_KEY"] = key
        try:
            return Historical()
        except Exception as e:
            raise RuntimeError(f"[databento] Could not create Historical client: {e}")

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from pathlib import Path

# --- Robust Databento import (works across client versions) ---
_HIST_CLS = None
try:
    # Newer style
    from databento import Historical as _Historical
    _HIST_CLS = _Historical
except Exception:
    try:
        # Older style
        from databento.historical import Historical as _Historical
        _HIST_CLS = _Historical
    except Exception:
        _HIST_CLS = None


DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LEVELS_FILE = DATA_DIR / "levels.json"

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


@dataclass
class DayLevels:
    date: str
    pdh: float | None = None     # Previous RTH day high (09:30-16:00 ET)
    pdl: float | None = None     # Previous RTH day low
    asia_high: float | None = None  # 20:00-00:00 ET
    asia_low: float | None = None
    london_high: float | None = None # 02:00-05:00 ET
    london_low: float | None = None


def _prev_business_date(d: datetime) -> datetime:
    """Return previous business date (Mon-Fri) in ET (strip time)."""
    x = d
    while True:
        x -= timedelta(days=1)
        if x.weekday() < 5:  # 0=Mon ... 4=Fri
            return x.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=ET)


def _et_window_to_utc(day_et: datetime, start_hm: tuple[int,int], end_hm: tuple[int,int]) -> tuple[datetime, datetime]:
    """Given an ET date and (start,end) hh:mm in ET, return UTC datetimes."""
    s = day_et.replace(hour=start_hm[0], minute=start_hm[1], second=0, microsecond=0, tzinfo=ET)
    e = day_et.replace(hour=end_hm[0], minute=end_hm[1], second=0, microsecond=0, tzinfo=ET)
    return s.astimezone(UTC), e.astimezone(UTC)


def _query_hi_lo(h, dataset: str, schema: str, symbol: str, start_utc: datetime, end_utc: datetime, verbose=False):
    """Query Databento ohlcv-1m and return (hi, lo) or (None, None) if empty."""
    store = h.timeseries.get_range(
        dataset=dataset,
        schema=schema,
        symbols=symbol,
        start=start_utc.isoformat(),
        end=end_utc.isoformat(),
    )
    df = store.to_df()
    if df.empty:
        if verbose:
            print(f"[rows=0] {start_utc.isoformat()} -> {end_utc.isoformat()}")
        return None, None
    hi = float(df["high"].max())
    lo = float(df["low"].min())
    if verbose:
        print(f"[rows={len(df)}] {start_utc.isoformat()} -> {end_utc.isoformat()} hi={hi} lo={lo}")
    return hi, lo


def build_levels(date: str | None = None, verbose: bool = False) -> DayLevels:
    """
    Compute PDH/PDL (prev RTH 09:30-16:00 ET), ASIA (20:00-00:00 ET), LONDON (02:00-05:00 ET)
    for FRONT_SYMBOL against GLBX.MDP3 + ohlcv-1m. Writes data/levels.json.
    """
    # --- env ---
    api_key = os.getenv("DATABENTO_API_KEY") or os.getenv("DATABENTO_API_KEY".lower())
    dataset = os.getenv("DB_DATASET", "GLBX.MDP3")
    schema = os.getenv("DB_SCHEMA", "ohlcv-1m")
    symbol = os.getenv("FRONT_SYMBOL") or os.getenv("FRONT_SYMBOL".lower())

    if not api_key:
        raise RuntimeError("DATABENTO_API_KEY is not set.")
    if not symbol:
        raise RuntimeError("FRONT_SYMBOL is not set (e.g., NQZ5).")

    # --- date (ET) ---
    if date:
        # Accept YYYY-MM-DD
        y, m, d = map(int, date.split("-"))
        day_et = datetime(y, m, d, tzinfo=ET)
    else:
        # default to 'today' in ET (strip time)
        now_et = datetime.now(ET)
        day_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)

    # --- windows in ET ---
    # ASIA: 20:00 -> 00:00 on the same "ET day" (start is previous calendar evening)
    asia_start_et = (day_et - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    asia_end_et   = day_et.replace(hour=0,  minute=0, second=0, microsecond=0)

    # LONDON: 02:00 -> 05:00 on the ET day
    lond_start_et = day_et.replace(hour=2, minute=0, second=0, microsecond=0)
    lond_end_et   = day_et.replace(hour=5, minute=0, second=0, microsecond=0)

    # PDH/PDL: previous business day RTH 09:30 -> 16:00 ET
    prev_et = _prev_business_date(day_et)
    rth_start_et = prev_et.replace(hour=9, minute=30, second=0, microsecond=0)
    rth_end_et   = prev_et.replace(hour=16, minute=0, second=0, microsecond=0)

    # --- to UTC ---
    asia_s_utc, asia_e_utc   = asia_start_et.astimezone(UTC), asia_end_et.astimezone(UTC)
    lond_s_utc, lond_e_utc   = lond_start_et.astimezone(UTC), lond_end_et.astimezone(UTC)
    rth_s_utc,  rth_e_utc    = rth_start_et.astimezone(UTC), rth_end_et.astimezone(UTC)

    if verbose:
        print("== WINDOWS (ET -> UTC) ==")
        print(f"ASIA   {asia_start_et} -> {asia_end_et}    | {asia_s_utc} -> {asia_e_utc}")
        print(f"LONDON {lond_start_et} -> {lond_end_et}    | {lond_s_utc} -> {lond_e_utc}")
        print(f"PDH/PDL(prev RTH) {rth_start_et} -> {rth_end_et} | {rth_s_utc} -> {rth_e_utc}")

    # --- Databento Historical ---
    if _HIST_CLS is None:
        raise RuntimeError("Databento Historical client not importable. Upgrade/install 'databento' package.")
    h = _get_databento_hist()

    # --- queries ---
    asia_hi, asia_lo     = _query_hi_lo(h, dataset, schema, symbol, asia_s_utc,  asia_e_utc,  verbose)
    london_hi, london_lo = _query_hi_lo(h, dataset, schema, symbol, lond_s_utc,  lond_e_utc,  verbose)
    pdh, pdl             = _query_hi_lo(h, dataset, schema, symbol, rth_s_utc,   rth_e_utc,   verbose)

    levels = DayLevels(
        date = day_et.date().isoformat(),
        pdh  = pdh,
        pdl  = pdl,
        asia_high   = asia_hi,
        asia_low    = asia_lo,
        london_high = london_hi,
        london_low  = london_lo,
    )
    # write file
    with open(LEVELS_FILE, "w") as f:
        json.dump(asdict(levels), f)
    return levels


def load_levels_json() -> DayLevels:
    if not LEVELS_FILE.exists():
        raise FileNotFoundError(f"{LEVELS_FILE} does not exist. Run build_levels first.")
    with open(LEVELS_FILE) as f:
        d = json.load(f)
    return DayLevels(**d)

