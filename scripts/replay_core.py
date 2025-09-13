#!/usr/bin/env python3
from __future__ import annotations

import pandas as _pd

def _sort_by_ts(df):
    """Return df sorted by UTC ts column, creating it if needed."""
    if df is None or getattr(df, "empty", True):
        return df
    if "ts" in df.columns:
        if not _pd.api.types.is_datetime64_any_dtype(df["ts"]):
            df["ts"] = _pd.to_datetime(df["ts"], utc=True, errors="coerce")
        return df.sort_values("ts")
    if "ts_event" in df.columns:
        df["ts"] = _pd.to_datetime(df["ts_event"], utc=True, errors="coerce")
        return df.sort_values("ts")
    if "ts_recv" in df.columns:
        df["ts"] = _pd.to_datetime(df["ts_recv"], utc=True, errors="coerce")
        return df.sort_values("ts")
    # fallback: use index
    if not df.index.name:
        df = df.reset_index().rename(columns={"index": "ts"})
    else:
        df = df.reset_index().rename(columns={df.index.name: "ts"})
    df["ts"] = _pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df.sort_values("ts")
import pandas as _pd


import os, sys, importlib
from pathlib import Path
from datetime import datetime, date, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd

# ---------------- .env loader (dotenv optional) ----------------
def _load_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # optional
        load_dotenv(env_path)
        return
    except Exception:
        pass
    # Manual KEY=VALUE parse
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ---------------- ENV ----------------
API_KEY = os.getenv("DATABENTO_API_KEY", "")
SYMBOL  = os.getenv("SYMBOL", "NQ")
SCHEMA  = os.getenv("SCHEMA", "ohlcv-1m")
DIVISOR = float(os.getenv("DIVISOR", "1"))
TZ_ET   = os.getenv("TIMEZONE", "America/New_York")
REPLAY_ET_DATE = os.getenv("REPLAY_ET_DATE")  # YYYY-MM-DD; default today ET

# Bind your pipeline explicitly via env:
#   export STRATEGY_FN="sbwatch.strategy.process_bar"
#   export ALERT_FN="sbwatch.alerts.dispatch"
STRATEGY_FQN = os.getenv("STRATEGY_FN", "")
ALERT_FQN    = os.getenv("ALERT_FN", "")

# Optional: send to test webhook instead of prod during replay
TEST_HOOK = os.getenv("DISCORD_WEBHOOK_URL_TEST", "")
if TEST_HOOK:
    os.environ["DISCORD_WEBHOOK_URL"] = TEST_HOOK

if not API_KEY:
    print("ERROR: DATABENTO_API_KEY missing.", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------- Use YOUR helpers/modules ----------------
# Databento client
try:
    from scripts.db_client import get_historical  # your helper
except Exception:
    from databento import Historical
    def get_historical(api_key: str | None = None):
        try:
            return Historical(api_key) if api_key else Historical()
        except TypeError:
            return Historical()

# capture_levels (must exist; your earlier logs reference it)
try:
    import scripts.capture_levels as cap
except Exception as e:
    print("ERROR: cannot import scripts.capture_levels: {}".format(e), file=sys.stderr)
    sys.exit(1)

# ---------------- Time helpers ----------------
def _et_time(hhmm: str) -> dtime:
    h, m = map(int, hhmm.split(":"))
    return dtime(h, m)

def make_utc_range(day_et: date, start_hhmm: str, end_hhmm: str, tz: str = TZ_ET):
    z = ZoneInfo(tz)
    s_local = datetime.combine(day_et, _et_time(start_hhmm), tzinfo=z)
    e_local = datetime.combine(day_et, _et_time(end_hhmm), tzinfo=z)
    if end_hhmm <= start_hhmm:  # crosses midnight
        e_local += timedelta(days=1)
    return s_local.astimezone(timezone.utc), e_local.astimezone(timezone.utc)

def avail_end() -> datetime:
    # stay behind the live edge to avoid 422 end_after_available_end
    return datetime.now(timezone.utc) - timedelta(seconds=120)

# ---------------- Resolver helpers ----------------
def _resolve_callable(fqn: str):
    if not fqn:
        return None
    mod_name, _, fn_name = fqn.rpartition(".")
    if not mod_name or not fn_name:
        return None
    m = importlib.import_module(mod_name)
    fn = getattr(m, fn_name, None)
    return fn if callable(fn) else None

def _bar_from_row(r: pd.Series):
    # Generic dict; adapt if your strategy expects a different shape
    return {
        "ts": pd.to_datetime(r["ts"]),
        "open": float(r["open"]),
        "high": float(r["high"]),
        "low": float(r["low"]),
        "close": float(r["close"]),
        "volume": float(r.get("volume", 0.0)),
        "symbol": SYMBOL,
        "schema": SCHEMA,
    }

# ---------------- Main ----------------
def main():
    cl = get_historical(API_KEY)

    # Choose ET date
    et_today = date.fromisoformat(REPLAY_ET_DATE) if REPLAY_ET_DATE else datetime.now(ZoneInfo(TZ_ET)).date()

    # Use YOUR levels builder (best-effort; we don t force success)
    try:
        _ = cap.build_levels_for_day(cl, et_today)
    except Exception as e:
        print("[replay] build_levels_for_day error: {}".format(e), file=sys.stderr)

    # Build full-day ET window, then clamp the END BEFORE calling your fetch_range
    day_s_utc, day_e_utc = make_utc_range(et_today, "00:00", "00:00")
    day_e_utc = min(day_e_utc, avail_end())

    # Use YOUR fetch_range to get bars
    if not hasattr(cap, "fetch_range"):
        print("ERROR: scripts.capture_levels is missing fetch_range().", file=sys.stderr)
        sys.exit(1)
    try:
        df = cap.fetch_range(cl, day_s_utc, day_e_utc)
    except Exception as e:
        print("ERROR: fetch_range failed: {}".format(e), file=sys.stderr)
        sys.exit(1)

    # Normalize (only if needed)
    for c in ("open","high","low","close"):
        if c in df.columns:
            df[c] = df[c] / DIVISOR
    if "ts" not in df.columns:
        df = df.reset_index().rename(columns={"ts_recv":"ts"})
    df = _ensure_ts_col(df); import pandas as _pd
try:
    import pandas as _pd
except NameError:
    # df not created yet; skip for now — later code can sort after fetch
    pass

# df already created abovedf = _sort_by_ts(df)
if __name__ == "__main__":
    main()


def _ensure_ts_col(df):
    """Ensure df has a UTC datetime column named 'ts'. Returns mutated df."""
    if df is None or getattr(df, "empty", True):
        return df
    # If ts already exists, try to ensure datetime
