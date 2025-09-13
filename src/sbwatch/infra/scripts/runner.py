#!/usr/bin/env python3
import os, time, subprocess
from datetime import datetime, timedelta
from dateutil import tz

NY = tz.gettz("America/New_York")
PYTHON = "/opt/sb-watchbot/.venv/bin/python"
MODULE = "-m"
APP    = "sbw.app"

US_START = (9, 30)   # 09:30 ET
US_END   = (16, 0)   # 16:00 ET

def now_et():
    return datetime.now(tz=NY)

def in_us_session(dt):
    s = dt.replace(hour=US_START[0], minute=US_START[1], second=0, microsecond=0)
    e = dt.replace(hour=US_END[0], minute=US_END[1], second=0, microsecond=0)
    return s <= dt <= e

def seconds_to_next_session(dt):
    s_today = dt.replace(hour=US_START[0], minute=US_START[1], second=0, microsecond=0)
    if dt < s_today:
        return max(5, int((s_today - dt).total_seconds()))
    # next day 09:30
    next_day = (dt + timedelta(days=1)).replace(hour=US_START[0], minute=US_START[1],
                                                second=0, microsecond=0)
    return max(5, int((next_day - dt).total_seconds()))

def main():
    while True:
        now = now_et()
        if not in_us_session(now):
            sleep_s = seconds_to_next_session(now)
            print(f"[runner] Out of session ({now.strftime('%H:%M:%S ET')}), sleeping {sleep_s}s...")
            time.sleep(sleep_s)
            continue

        print("[runner] Launching sbw.app for live session...")
        code = subprocess.call([PYTHON, MODULE, APP])
        # If the app exits (network hiccup, DB limit, etc.), wait a bit and retry.
        print(f"[runner] sbw.app exited with code {code}; backing off 15s.")
        time.sleep(15)

if __name__ == "__main__":
    main()
