import re
from databento.common.error import BentoClientError
from datetime import date, datetime, time, timedelta, timezone

def _provider_guard_now():
    """Return a UTC timestamp slightly behind live to avoid 422s."""
    return datetime.now(timezone.utc) - timedelta(seconds=120)

#!/usr/bin/env python3
import os, json, sys, traceback

def _et_time(hhmm: str) -> time:
    h, m = map(int, hhmm.split(":"))
    return time(hour=h, minute=m)

def make_utc_range(day_et: date, start_hhmm: str, end_hhmm: str, tz: str = "America/New_York") -> tuple[datetime, datetime]:
    # Build half-open [start, end) in UTC for an ET session anchored to ET date.
    # If end <= start, roll end to next ET day (handles midnight crossover).
    z = ZoneInfo(tz)
    s_local = datetime.combine(day_et, _et_time(start_hhmm), tzinfo=z)
    e_local = datetime.combine(day_et, _et_time(end_hhmm), tzinfo=z)
    if end_hhmm <= start_hhmm:
        e_local = e_local + timedelta(days=1)
    s_utc = s_local.astimezone(timezone.utc)
    e_utc = e_local.astimezone(timezone.utc)
    return s_utc, e_utc


from dataclasses import asdict
from scripts.db_client import get_historical
from zoneinfo import ZoneInfo

# --- Config from env ---
DATASET   = os.getenv("DB_DATASET",  "GLBX.MDP3")
SCHEMA    = os.getenv("DB_SCHEMA",   "ohlcv-1m")   # must be a valid timeseries schema
SYMBOL    = os.getenv("FRONT_SYMBOL","ES.f")
LEVELS_FP = "/opt/sb-watchbot/data/levels.json"
WEBHOOK   = os.getenv("DISCORD_WEBHOOK_URL", "")
DIVISOR   = float(os.getenv("PRICE_DIVISOR", "1000000"))
SAFETY_MINUTES = int(os.getenv("SB_SAFETY_MIN", "45"))  # margin from "now" for end clamp
ET        = ZoneInfo("America/New_York")

def notify(msg: str):
    """Post to Discord if configured; otherwise print to stderr."""
    if not WEBHOOK:
        print(msg, file=sys.stderr)
        return
    try:
        import requests
        r = requests.post(WEBHOOK, json={"content": msg}, timeout=10)
        print(f"Discord status: {r.status_code}")
    except Exception:
        print("Discord POST failed:\n" + traceback.format_exc(), file=sys.stderr)

def session_window_utc(d: date, which: str) -> tuple[datetime, datetime]:
    """Return [start,end] in UTC for a named session on ET calendar day d."""
    if which == "london":
        s = datetime.combine(d, time(2,0), ET)
        e = datetime.combine(d, time(5,0), ET)
    elif which == "asia":
        s = datetime.combine(d, time(18,0), ET)
        e = datetime.combine(d + timedelta(days=1), time(0,0), ET)
    else:
        raise ValueError("unknown session")
    return s.astimezone(timezone.utc), e.astimezone(timezone.utc)

def clamp_end(end_utc) -> datetime:
    """Clamp end to 'now - SAFETY_MINUTES' to avoid 422 after-available-range."""
    now_utc = datetime.now(timezone.utc)
    guard   = now_utc - timedelta(minutes=SAFETY_MINUTES)
    return min(end_utc, guard)

def fetch_range(client, start_utc: datetime, end_utc: datetime):
    """Fetch OHLCV via Databento HTTP Historical API with provider-edge guards."""
    import os
    # client
    if client is None:
        key = os.getenv("DATABENTO_API_KEY", "")
        if not key or not key.startswith("db-"):
            raise RuntimeError("DATABENTO_API_KEY is empty or malformed")
        client = get_historical(key)

    # clamp to provider "now"
    guard = _provider_guard_now()
    if end_utc > guard:
        end_utc = guard
    if start_utc >= guard:
        start_utc = guard - timedelta(minutes=1)
    if end_utc <= start_utc:
        start_utc = end_utc - timedelta(minutes=1)

    # instrument (prefer CONTRACT; fallback SYMBOL; default a plausible front)
    symbol = os.getenv("CONTRACT") or os.getenv("SYMBOL", "NQU5")
    schema = os.getenv("SCHEMA", "ohlcv-1m")

    # try once, then retry on 422 with advertised end
    try:
        df = client.timeseries.get_range(
            dataset="GLBX.MDP3",
            symbols=symbol,
            schema=schema,
            start=start_utc,
            end=end_utc,
        ).to_df()
    except BentoClientError as e:
        m = re.search(r"available up to '([^']+)'", str(e))
        if not m:
            raise
        from pandas import to_datetime
        end_retry = to_datetime(m.group(1)).to_pydatetime()
        if end_retry <= start_utc:
            end_retry = start_utc + timedelta(minutes=1)
        df = client.timeseries.get_range(
            dataset="GLBX.MDP3",
            symbols=symbol,
            schema=schema,
            start=start_utc,
            end=end_retry,
        ).to_df()

    return df

    """Fetch historical bars via Databento HTTP Historical API.

    - If client is None, build it using .
    - Ensure end_utc > start_utc (roll end by +1 day if needed).
    - Clamp end_utc with clamp_end() to avoid provider edge (422).
    """
    import os

    # Build client if needed
    if client is None:
        key = os.getenv("DATABENTO_API_KEY", "")
        if not key or not key.startswith("db-"):
            raise RuntimeError("DATABENTO_API_KEY is empty or malformed")
        client = get_historical(key)
    # --- Provider availability guard (handles midday replays) ---
    guard = _provider_guard_now()
    if end_utc > guard:
        end_utc = guard
    if start_utc >= guard:
        # pull start just before guard to keep a valid window
        start_utc = guard - timedelta(minutes=1)
    if end_utc <= start_utc:
        start_utc = end_utc - timedelta(minutes=1)

    # Clamp to provider availability (final pass)
    end_utc = clamp_end(end_utc)

    # Env-driven symbols/schema; dataset fixed to GLBX.MDP3
    symbol = os.getenv("SYMBOL", "NQ")
    schema = os.getenv("SCHEMA", "ohlcv-1m")

    return client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=symbol,
        schema=schema,
        start=start_utc,
        end=end_utc,
    ).to_df()

def build_levels_for_day(client, day_et):
    """Compute Asia/London/Prev-Day highs/lows using clamped fetch_range.

    Returns a dict like:
    {
      "Asia":   {"high": float, "low": float},
      "London": {"high": float, "low": float},
      "Prev":   {"high": float, "low": float},
    }
    """
    import math
    import pandas as pd

    # Session windows (ET)
    asia_s,   asia_e   = make_utc_range(day_et, "18:00", "00:00")
    london_s, london_e = make_utc_range(day_et, "02:00", "05:00")
    prev_s,   prev_e   = make_utc_range(day_et - timedelta(days=1), "09:30", "16:00")

    out = {"Asia": {"high": math.nan, "low": math.nan},
           "London": {"high": math.nan, "low": math.nan},
           "Prev": {"high": math.nan, "low": math.nan}}

    def _hl(df: pd.DataFrame):
        if df is None or df.empty:
            return math.nan, math.nan
        return float(df["high"].max()), float(df["low"].min())

    try:
        a = fetch_range(client, asia_s, asia_e)
        h, l = _hl(a)
        out["Asia"]["high"] = h; out["Asia"]["low"] = l
    except Exception as e:
        # leave NaNs; caller may log
        pass

    try:
        ldn = fetch_range(client, london_s, london_e)
        h, l = _hl(ldn)
        out["London"]["high"] = h; out["London"]["low"] = l
    except Exception:
        pass

    try:
        prv = fetch_range(client, prev_s, prev_e)
        h, l = _hl(prv)
        out["Prev"]["high"] = h; out["Prev"]["low"] = l
    except Exception:
        pass

    return out
def save_levels(d: date, payload: dict):
    os.makedirs(os.path.dirname(LEVELS_FP), exist_ok=True)
    if os.path.exists(LEVELS_FP):
        try:
            data = json.load(open(LEVELS_FP))
        except Exception:
            data = {}
    else:
        data = {}
    key = d.strftime("%Y-%m-%d")
    data[key] = payload
    with open(LEVELS_FP, "w") as f:
        json.dump(data, f, indent=2)

def main():
    # build Historical client
    key = os.getenv("DATABENTO_API_KEY", "")
    if not key or not key.startswith("db-"):
        raise RuntimeError("DATABENTO_API_KEY is empty or malformed")
    client = get_historical(key)

    today_et = datetime.now(ET).date()
    levels = build_levels_for_day(client, today_et)
    save_levels(today_et, levels)

    msg = (
        f"📈 SB Watchbot levels captured for {today_et}\n"
        f"• Asia H/L: {levels['asia']['high']} / {levels['asia']['low']}\n"
        f"• London H/L: {levels['london']['high']} / {levels['london']['low']}"
    )
    notify(msg)
    print("OK")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        notify(f"⚠️ SB Watchbot levels capture FAILED:\n```{traceback.format_exc()[-1800:]}```")
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)
