#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from databento import Historical

DATASET   = "GLBX.MDP3"
SCHEMA    = "ohlcv-1m"   # 1-minute bars; change if you want different
OUT_PATH  = "/opt/sb-watchbot/data/levels.json"

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# Asia & London session windows (ET, 24h)
ASIA_START  = time(18, 0)  # 6:00pm ET
ASIA_END    = time(0, 0)   # midnight ET
LDN_START   = time(2, 0)   # 2:00am ET
LDN_END     = time(5, 0)   # 5:00am ET

@dataclass
class Session:
    start: time
    end: time

ASIA   = Session(ASIA_START, ASIA_END)
LONDON = Session(LDN_START, LDN_END)

def dt_et(d: datetime) -> datetime:
    return d.astimezone(ET)

def midnight_et(d: datetime) -> datetime:
    d_et = dt_et(d)
    return datetime(d_et.year, d_et.month, d_et.day, tzinfo=ET)

def session_window(day_et: datetime, s: Session) -> tuple[datetime, datetime]:
    """Return ET datetimes spanning a session inside a single calendar day block.
    Handles ASIA crossing midnight."""
    start = datetime.combine(day_et.date(), s.start, tzinfo=ET)
    end   = datetime.combine(day_et.date(), s.end,   tzinfo=ET)
    # Asia crosses midnight: if end <= start, the end is on the following ET day
    if end <= start:
        end = end + timedelta(days=1)
    return start, end

def to_utc(dt_et_: datetime) -> datetime:
    return dt_et_.astimezone(UTC)

def fetch_1m(api: Historical, symbol: str, start_utc: datetime, end_utc: datetime):
    # Keep it simple; we’ll let any HTTP error bubble up to the retry logic
    return list(api.timeseries.get_range(
        dataset=DATASET,
        schema=SCHEMA,
        symbols=[symbol],
        start=start_utc,
        end=end_utc,
    ))

def hi_lo(rows, price_field="close"):
    hi = float("-inf"); lo = float("inf")
    for r in rows:
        px = float(getattr(r, price_field, r.get(price_field)))  # works for both objects & dicts
        if px > hi: hi = px
        if px < lo: lo = px
    if hi == float("-inf"):
        return None, None
    return hi, lo

def build_for_day(api: Historical, symbol: str, day_et: datetime) -> dict:
    out: dict = {"asia": {}, "london": {}, "prev_day": {}}

    # Asia session (ET, can cross midnight)
    a_lo_et, a_hi_et = session_window(day_et, ASIA)
    a_rows = fetch_1m(api, symbol, to_utc(a_lo_et), to_utc(a_hi_et))
    a_hi, a_lo = hi_lo(a_rows)
    if a_hi is None:
        raise RuntimeError("No Asia rows returned")

    # London session (same ET day)
    l_lo_et, l_hi_et = session_window(day_et, LONDON)
    l_rows = fetch_1m(api, symbol, to_utc(l_lo_et), to_utc(l_hi_et))
    l_hi, l_lo = hi_lo(l_rows)
    if l_hi is None:
        raise RuntimeError("No London rows returned")

    # Previous ET day hi/lo (midnight-to-midnight)
    prev0 = midnight_et(day_et - timedelta(days=1))
    prev1 = prev0 + timedelta(days=1)
    p_rows = fetch_1m(api, symbol, to_utc(prev0), to_utc(prev1))
    p_hi, p_lo = hi_lo(p_rows)
    if p_hi is None:
        p_hi = p_lo = 0.0

    out["asia"]    = {"high": a_hi, "low": a_lo, "start": ASIA_START.strftime("%H:%M"),  "end": ASIA_END.strftime("%H:%M")}
    out["london"]  = {"high": l_hi, "low": l_lo, "start": LDN_START.strftime("%H:%M"),   "end": LDN_END.strftime("%H:%M")}
    out["prev_day"] = {"high": p_hi, "low": p_lo}
    return out

def main():
    symbol = os.environ.get("FRONT_SYMBOL") or "NQZ5"   # your front
    api_key = os.environ.get("DATABENTO_API_KEY") or ""
    if not api_key:
        raise SystemExit("DATABENTO_API_KEY not set in env")

    api = Historical(key=api_key)

    # Today's ET (date key e.g., "2025-09-10")
    now_et = dt_et(datetime.now(tz=UTC))
    today_key = now_et.strftime("%Y-%m-%d")
    day_et = midnight_et(now_et)

    # Try today's Asia day first; if unavailable, back up one day (avoids 422)
    tried = []
    for offset in (0, 1):
        try_day = day_et - timedelta(days=offset)
        try_key = try_day.strftime("%Y-%m-%d")
        tried.append(try_key)
        try:
            levels = build_for_day(api, symbol, try_day)
            # Write atomically
            tmp_path = OUT_PATH + ".tmp"
            if os.path.exists(OUT_PATH):
                with open(OUT_PATH, "r") as f:
                    data = json.load(f)
            else:
                data = {}
            data[try_key] = levels
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, OUT_PATH)
            print(f"Levels OK for {try_key} -> {OUT_PATH}")
            return
        except Exception as e:
            print(f"Build failed for {try_key}: {e}")

    raise SystemExit(f"Could not build levels for any of: {tried}")

if __name__ == "__main__":
    main()
