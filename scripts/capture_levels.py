#!/usr/bin/env python3
import os, json, sys, traceback
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
import databento as db

DATASET   = os.getenv("DB_DATASET",  "GLBX.MDP3")
SCHEMA    = os.getenv("DB_SCHEMA",   "ohlcv-1m")
SYMBOL    = os.getenv("FRONT_SYMBOL","NQU5")
LEVELS_FP = "/opt/sb-watchbot/data/levels.json"
WEBHOOK   = os.getenv("DISCORD_WEBHOOK_URL", "")
DIVISOR   = float(os.getenv("PRICE_DIVISOR", "1000000000"))  # 1e9 (nanodollars)
SAFETY_MINUTES = int(os.getenv("SB_SAFETY_MIN", "45"))
ET = ZoneInfo("America/New_York")

def notify(msg: str):
    if not WEBHOOK:
        print(msg, file=sys.stderr); return
    try:
        import requests
        r = requests.post(WEBHOOK, json={"content": msg}, timeout=10)
        print("Discord status:", r.status_code)
    except Exception:
        print("Discord POST failed:\n" + traceback.format_exc(), file=sys.stderr)

def session_window_utc(d: date, which: str):
    # london: 02:00–05:00 ET on d
    # asia  : 18:00–00:00 ET from (d-1) -> d
    if which == "london":
        s = datetime.combine(d, time(2,0), ET)
        e = datetime.combine(d, time(5,0), ET)
    elif which == "asia":
        s = datetime.combine(d - timedelta(days=1), time(18,0), ET)
        e = datetime.combine(d,                   time(0,0),  ET)
    else:
        raise ValueError(which)
    return s.astimezone(timezone.utc), e.astimezone(timezone.utc)

def fetch_range(client, start_utc, end_utc):
    safe_now = datetime.now(timezone.utc) - timedelta(minutes=SAFETY_MINUTES)
    effective_end = min(end_utc, safe_now)
    if effective_end <= start_utc:
        return []
    return client.timeseries.get_range(
        dataset=DATASET, symbols=[SYMBOL], schema=SCHEMA,
        start=start_utc, end=effective_end
    )

def build_levels_for_day(client, d: date):
    out = {
        "asia":   {"high": 0.0, "low": 0.0, "start": "18:00", "end": "00:00"},
        "london": {"high": 0.0, "low": 0.0, "start": "02:00", "end": "05:00"},
        "prev_day": {"high": 0.0, "low": 0.0},
    }
    for name in ("asia","london"):
        s_utc, e_utc = session_window_utc(d, name)
        hi = lo = None
        for r in fetch_range(client, s_utc, e_utc):
            h = getattr(r, "high", None); l = getattr(r, "low", None)
            if isinstance(r, dict):
                h = r.get("high", h); l = r.get("low", l)
            if h is None or l is None: continue
            hi = h if hi is None else max(hi, h)
            lo = l if lo is None else min(lo, l)
        if hi is not None and lo is not None:
            out[name]["high"] = round(float(hi)/DIVISOR, 2)
            out[name]["low"]  = round(float(lo)/DIVISOR, 2)
    return out

def save_levels(d: date, payload: dict):
    os.makedirs(os.path.dirname(LEVELS_FP), exist_ok=True)
    data = {}
    if os.path.exists(LEVELS_FP):
        try: data = json.load(open(LEVELS_FP))
        except Exception: data = {}
    data[d.strftime("%Y-%m-%d")] = payload
    json.dump(data, open(LEVELS_FP,"w"), indent=2)

def main():
    key = os.getenv("DATABENTO_API_KEY","")
    if not key or not key.startswith("db-"):
        raise RuntimeError("DATABENTO_API_KEY is empty or malformed")
    client = db.Historical(key)
    today = datetime.now(ET).date()
    levels = build_levels_for_day(client, today)
    save_levels(today, levels)
    notify(
        f"📈 SB Watchbot levels captured for {today}\n"
        f"• Asia H/L: {levels['asia']['high']} / {levels['asia']['low']}\n"
        f"• London H/L: {levels['london']['high']} / {levels['london']['low']}"
    )
    print("OK")

if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback
        notify(f"⚠️ SB Watchbot levels capture FAILED:\n```{traceback.format_exc()[-1800:]}```")
        sys.exit(1)
