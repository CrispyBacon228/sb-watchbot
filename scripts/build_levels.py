#!/usr/bin/env python3
from __future__ import annotations

# --- begin replay safety helpers ---
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

def _et_window_to_utc(et_date_str: str, start_hhmm: str, end_hhmm: str):
    # et_date_str like "2025-09-12"; hhmm like "09:30", "11:00"
    et = ZoneInfo("America/New_York")
    y,m,d = map(int, et_date_str.split("-"))
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    start_et = datetime(y,m,d,sh,sm, tzinfo=et)
    end_et   = datetime(y,m,d,eh,em, tzinfo=et)
    return start_et.astimezone(timezone.utc), end_et.astimezone(timezone.utc)

def _clamp_range(start_utc, end_utc, safety_min=10):
    # Do not ask past "now - safety"
    now_guard = datetime.now(timezone.utc) - timedelta(minutes=safety_min)
    if end_utc > now_guard:
        end_utc = now_guard
    # Ensure start < end
    if start_utc >= end_utc:
        start_utc = end_utc - timedelta(minutes=1)
    return start_utc, end_utc
# --- end replay safety helpers ---

# === SB clamp helpers (idempotent) ===
from datetime import datetime, timezone, timedelta
_SBW_CLAMP_HELPERS = True

SAFETY_SECONDS = 60  # don’t query right up to "now"

def _clamp_utc_range(start_utc, end_utc):
    # Normalize Nones
    if end_utc is None:
        end_utc = datetime.now(timezone.utc) - timedelta(seconds=SAFETY_SECONDS)
    if start_utc is None:
        start_utc = end_utc - timedelta(hours=5)
    # Fix inverted / zero width
    if start_utc >= end_utc:
        start_utc = end_utc - timedelta(hours=5)
    return start_utc, end_utc

def _get_range(client, start_utc=None, end_utc=None, **kw):
    # Always clamp first
    start_utc, end_utc = _clamp_utc_range(start_utc, end_utc)
    try:
        return _get_range(client, start=start_utc, end=end_utc, **kw)
    except Exception as e:
        msg = str(e)
        # Heal only time-availability problems; anything else -> re-raise
        if ("data_start_after_available_end" not in msg and
            "data_end_after_available_end"   not in msg and
            "Invalid time range query"       not in msg):
            raise
        # Back off end and ensure a sane window, then retry once
        end2 = end_utc - timedelta(minutes=30)
        if end2 <= start_utc:
            start_utc = end2 - timedelta(hours=1)
        return _get_range(client, start=start_utc, end=end2, **kw)
# === end helpers ===

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
    # _BUILD_ET_WINDOW_BEGIN
    import os
    et_date = os.environ.get("REPLAY_ET_DATE")  # preferred for replay
    if not et_date:
        # default to "today" in ET
        et = ZoneInfo("America/New_York")
        et_date = datetime.now(et).strftime("%Y-%m-%d")
    # Your analysis window: 09:30–11:00 ET
    s_utc, e_utc = _et_window_to_utc(et_date, "09:30", "11:00")
    s_utc, e_utc = _clamp_range(s_utc, e_utc, safety_min=10)
    # _BUILD_ET_WINDOW_END
    symbol = os.environ.get("FRONT_SYMBOL") or "NQZ5"   # your front
    api_key = os.environ.get("DATABENTO_API_KEY") or ""
    if not api_key:
        raise SystemExit("DATABENTO_API_KEY not set in env")

    api = Historical(api_key)

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
