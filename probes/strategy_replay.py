#!/usr/bin/env python3
import os, sys, json, csv
from pathlib import Path
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

# import your actual strategy + notifier
from src.sbwatch.strategy import SBEngine
from src.sbwatch import notify as _notify

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

# add a tiny wrapper so we also see posts in the console during replay
_real_post = _notify.post_discord
def _wrapped_post(msg: str):
    print(f"[REPLAY] would post -> {msg.splitlines()[0]}", flush=True)
    return _real_post(msg)
_notify.post_discord = _wrapped_post  # monkey-patch, only in this process

def load_levels():
    with open(ROOT/"data"/"levels.json","r") as f:
        return json.load(f)

def iter_csv(path: Path):
    def parse_ts(s):
        s = str(s).strip()
        if s.isdigit() and len(s) >= 12: return int(s)           # unix ms
        if s.isdigit():                    return int(s)*1000     # unix sec
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return int(dt.timestamp()*1000)
    with open(path,"r",newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            yield (
                parse_ts(row["ts"]),
                float(row["open"]), float(row["high"]),
                float(row["low"]),  float(row["close"])
            )

def iter_stdin():
    for line in sys.stdin:
        line=line.strip()
        if not line: continue
        o=json.loads(line)
        ts=o["ts"]
        if isinstance(ts,str):
            dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
            if dt.tzinfo is None:
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            ts_ms=int(dt.timestamp()*1000)
        elif ts>10_000_000_000: ts_ms=int(ts)
        else: ts_ms=int(ts)*1000
        yield ts_ms, float(o["open"]), float(o["high"]), float(o["low"]), float(o["close"])

def within_am_window(ts_ms:int):
    dt = datetime.fromtimestamp(ts_ms/1000, tz=ZoneInfo("UTC")).astimezone(ET)
    t = dt.timetz()
    return dtime(10,0,0) <= t.replace(tzinfo=None) < dtime(11,0,0)

def main():
    lv = load_levels()
    eng = SBEngine(lv)

    # Source: CSV or stdin
    bar_csv = os.getenv("BAR_CSV")
    src = iter_csv(Path(bar_csv)) if bar_csv else iter_stdin()

    # Feed bars exactly like live would
    for ts,o,h,l,c in src:
        eng.on_bar(ts,o,h,l,c)

if __name__ == "__main__":
    main()
