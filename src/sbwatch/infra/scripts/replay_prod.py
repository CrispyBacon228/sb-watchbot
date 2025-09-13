#!/usr/bin/env python3
from __future__ import annotations
import os, sys, importlib
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, date, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd
# Prefer your levels/session builder
try:
    from scripts.capture_levels import build_levels_for_day  # type: ignore
    _HAVE_BUILD_LEVELS = True
except Exception:
    build_levels_for_day = None
    _HAVE_BUILD_LEVELS = False

from dataclasses import dataclass

# -----------------------
# Robust .env loader
# -----------------------
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
    for line in env_path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v = line.split("=",1)
        os.environ.setdefault(k.strip(), v.strip())
_load_env()

# -----------------------
# Config (env-driven)
# -----------------------
API_KEY = os.getenv("DATABENTO_API_KEY", "")
SYMBOL  = os.getenv("SYMBOL", "NQ")
SCHEMA  = os.getenv("SCHEMA", "ohlcv-1m")
DIVISOR = float(os.getenv("DIVISOR", "1"))
TZ_ET   = os.getenv("TIMEZONE", "America/New_York")
REPLAY_ET_DATE = os.getenv("REPLAY_ET_DATE")  # YYYY-MM-DD; default today ET

# Optional: route alerts to a test webhook without touching prod
TEST_HOOK = os.getenv("DISCORD_WEBHOOK_URL_TEST", "")
if TEST_HOOK:
    os.environ["DISCORD_WEBHOOK_URL"] = TEST_HOOK

if not API_KEY:
    print("ERROR: DATABENTO_API_KEY missing.", file=sys.stderr)
    sys.exit(2)

# Ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# -----------------------
# Databento client helper
# -----------------------
try:
    # prefer your helper if present
    from scripts.db_client import get_historical  # type: ignore
except Exception:
    from databento import Historical
    def get_historical(api_key: str | None = None):
        try:
            return Historical(api_key) if api_key else Historical()
        except TypeError:
            return Historical()

# -----------------------
# Time helpers
# -----------------------
def _et_time(hhmm: str) -> dtime:
    h, m = map(int, hhmm.split(":"))
    return dtime(h, m)

def make_utc_range(day_et: date, start_hhmm: str, end_hhmm: str, tz: str = TZ_ET):
    z = ZoneInfo(tz)
    s_local = datetime.combine(day_et, _et_time(start_hhmm), tzinfo=z)
    e_local = datetime.combine(day_et, _et_time(end_hhmm), tzinfo=z)
    if end_hhmm <= start_hhmm:
        e_local += timedelta(days=1)
    return s_local.astimezone(timezone.utc), e_local.astimezone(timezone.utc)

@dataclass
class Levels:
    asia_hi: float; asia_lo: float
    london_hi: float; london_lo: float
    prev_hi: float; prev_lo: float

def avail_end() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=90)

# -----------------------
# Fetch OHLCV (clamped)
# -----------------------
def fetch_ohlcv(start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    cl = get_historical(API_KEY)
    end_utc = min(end_utc, avail_end())
    df = cl.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=SYMBOL,
        schema=SCHEMA,
        start=start_utc,
        end=end_utc,
    ).to_df()
    for c in ("open","high","low","close"):
        if c in df.columns:
            df[c] = df[c] / DIVISOR
    if "ts" not in df.columns:
        df = df.reset_index().rename(columns={"ts_recv":"ts"})
    return df.sort_values("ts")

# -----------------------
# Bind to YOUR strategy + alerts
# -----------------------
def _resolve_strategy():
    """
    Try common module+function names. Return (module, func_name, callable).
    """
    candidates = [
        ("sbwatch.strategy", "process_bar"),
        ("sbwatch.strategy", "on_bar"),
        ("sbwatch.strategy", "handle_bar"),
        ("sbwatch.strategy", "run_bar"),
        ("strategy", "process_bar"),
        ("strategy", "on_bar"),
        ("strategy", "handle_bar"),
        ("strategy", "run_bar"),
    ]
    for mod, fn in candidates:
        try:
            m = importlib.import_module(mod)
            f = getattr(m, fn, None)
            if callable(f):
                return (mod, fn, f)
        except Exception:
            continue
    return (None, None, None)

def _resolve_alert_sender():
    """
    Try to find your alert dispatch function.
    Return (module, func_name, callable) or (None, None, print).
    """
    candidates = [
        ("sbwatch.alerts", "dispatch"),
        ("sbwatch.alerts", "send_alert"),
        ("sbwatch.alerts", "emit"),
        ("sbwatch.alerts", "send"),
        ("alerts", "dispatch"),
        ("alerts", "send_alert"),
        ("alerts", "emit"),
        ("alerts", "send"),
    ]
    for mod, fn in candidates:
        try:
            m = importlib.import_module(mod)
            f = getattr(m, fn, None)
            if callable(f):
                return (mod, fn, f)
        except Exception:
            continue
    # fallback: just print
    return (None, None, lambda msg: print(msg if isinstance(msg, str) else repr(msg)))

STRAT_MOD, STRAT_FN, STRAT_CALL = _resolve_strategy()
ALERT_MOD, ALERT_FN, ALERT_CALL = _resolve_alert_sender()

print(f"[replay] strategy: {STRAT_MOD}.{STRAT_FN}" if STRAT_CALL else "[replay] strategy: NOT FOUND")
print(f"[replay] alerts  : {ALERT_MOD}.{ALERT_FN}" if ALERT_CALL else "[replay] alerts  : print() fallback")

# -----------------------
# Bar adapter
# -----------------------
def _bar_from_row(r: pd.Series):
    # generic dict; adapt as needed by your strategy
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

# -----------------------
# Replay main
# -----------------------
def main():
    et_now = datetime.now(ZoneInfo(TZ_ET))
    day_et = date.fromisoformat(REPLAY_ET_DATE) if REPLAY_ET_DATE else et_now.date()

    day_s_utc, day_e_utc = make_utc_range(day_et, "00:00", "00:00")
    day_e_utc = min(day_e_utc, avail_end())  # clamp

    print(f"[replay] {SYMBOL} {SCHEMA} {day_et} (ET)")
    df = fetch_ohlcv(day_s_utc, day_e_utc)
    if df.empty:
        print("[replay] No data returned for this window.")
        return

    # If you have any init hooks, try to call them (best-effort)
    for init_mod, init_fn in [("sbwatch.strategy","init"), ("strategy","init")]:
        try:
            m = importlib.import_module(init_mod)
            f = getattr(m, init_fn, None)
            if callable(f):
                f()
                print(f"[replay] called {init_mod}.{init_fn}()")
                break
        except Exception:
            pass

    # Drive bars into your strategy and send alerts your way
    for _, row in df.iterrows():
        bar = _bar_from_row(row)
        produced = None
        try:
            if STRAT_CALL:
                produced = STRAT_CALL(bar)  # could be str / dict / list / None
        except Exception as e:
            print(f"[replay][strategy error] {e}", file=sys.stderr)
            continue

        # Normalize to iterable
        if produced is None:
            continue
        if isinstance(produced, (str, dict)):
            produced = [produced]
        if isinstance(produced, list):
            for item in produced:
                try:
                    ALERT_CALL(item)
                except Exception as e:
                    # as a last resort, print the item
                    print(f"[replay][alert error] {e}", file=sys.stderr)
                    print(item)

if __name__ == "__main__":
    main()


def compute_levels(day_et: date) -> Levels:
    """Use your capture_levels.build_levels_for_day when available."""
    if _HAVE_BUILD_LEVELS and build_levels_for_day:
        try:
            cl = get_historical(API_KEY)
            lv = build_levels_for_day(cl, day_et)  # your function
            # Accept either dict-like or object-like results
            def _get(d, k):
                try:
                    return float(d[k]) if isinstance(d, dict) else float(getattr(d, k))
                except Exception:
                    return float("nan")
            # The most common keys your report uses:
            asia_hi = _get(lv.get("Asia") if isinstance(lv, dict) else getattr(lv, "Asia", None), "high")
            asia_lo = _get(lv.get("Asia") if isinstance(lv, dict) else getattr(lv, "Asia", None), "low")
            london_hi = _get(lv.get("London") if isinstance(lv, dict) else getattr(lv, "London", None), "high")
            london_lo = _get(lv.get("London") if isinstance(lv, dict) else getattr(lv, "London", None), "low")
            prev_hi = _get(lv.get("Prev") if isinstance(lv, dict) else getattr(lv, "Prev", None), "high")
            prev_lo = _get(lv.get("Prev") if isinstance(lv, dict) else getattr(lv, "Prev", None), "low")
            return Levels(asia_hi, asia_lo, london_hi, london_lo, prev_hi, prev_lo)
        except Exception:
            pass  # fall through to local compute

    # Fallback: minimal compute using same ET windows
    a_s, a_e = make_utc_range(day_et, "18:00", "00:00")
    l_s, l_e = make_utc_range(day_et, "02:00", "05:00")
    y = day_et - timedelta(days=1)
    p_s, p_e = make_utc_range(y, "09:30", "16:00")
    a = fetch_ohlcv(a_s, a_e); l = fetch_ohlcv(l_s, l_e); p = fetch_ohlcv(p_s, p_e)
    return Levels(
        float(a["high"].max()) if not a.empty else float("nan"),
        float(a["low"].min())  if not a.empty else float("nan"),
        float(l["high"].max()) if not l.empty else float("nan"),
        float(l["low"].min())  if not l.empty else float("nan"),
        float(p["high"].max()) if not p.empty else float("nan"),
        float(p["low"].min())  if not p.empty else float("nan"),
    )

