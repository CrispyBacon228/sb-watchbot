#!/usr/bin/env python3
import os, sys, json, csv
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")

from src.sbwatch.strategy import SBEngine as _SBEngine
from src.sbwatch import notify as _notify

# echo webhook posts to console too
_real_post = _notify.post_discord
def _wrapped_post(msg: str):
    print(f"[POST] {msg.splitlines()[0]}", flush=True)
    return _real_post(msg)
_notify.post_discord = _wrapped_post

def load_levels():
    with open(ROOT/"data"/"levels.json","r") as f:
        return json.load(f)

def iter_csv(path: Path):
    def parse_ts(s):
        s=str(s).strip()
        if s.isdigit() and len(s)>=12: return int(s)
        if s.isdigit(): return int(s)*1000
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo
            dt=dt.replace(tzinfo=ZoneInfo("UTC"))
        return int(dt.timestamp()*1000)
    with open(path,"r",newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            yield parse_ts(row["ts"]), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

def iter_stdin():
    for line in sys.stdin:
        line=line.strip()
        if not line: continue
        o=json.loads(line)
        ts=o["ts"]
        if isinstance(ts,str):
            dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
            if dt.tzinfo is None:
                from zoneinfo import ZoneInfo
                dt=dt.replace(tzinfo=ZoneInfo("UTC"))
            ts=int(dt.timestamp()*1000)
        elif ts>10_000_000_000: ts=int(ts)
        else: ts=int(ts)*1000
        yield ts, float(o["open"]), float(o["high"]), float(o["low"]), float(o["close"])

def wrap_seed(eng):
    import math
    orig_disp = eng._is_displacement

    def seeded_disp(i:int, side:str) -> bool:
        # seed swings from prior bars if NaN
        if math.isnan(eng.swings.last_high) or math.isnan(eng.swings.last_low):
            if i >= 1:
                prev_high = max(b.h for b in eng.bars[:i])
                prev_low  = min(b.l for b in eng.bars[:i])
                eng.swings.last_high = prev_high
                eng.swings.last_low  = prev_low
        ok = orig_disp(i, side)
        print(f"[GATE] displacement@{i} side={side}: {ok} (last_high={eng.swings.last_high:.5f} last_low={eng.swings.last_low:.5f})", flush=True)
        return ok

    eng._is_displacement = seeded_disp
    return eng

def main():
    lv = load_levels()
    eng = _SBEngine(lv)
    eng = wrap_seed(eng)

    bar_csv = os.getenv("BAR_CSV")
    src = iter_csv(Path(bar_csv)) if bar_csv else iter_stdin()

    for ts,o,h,l,c in src:
        eng.on_bar(ts,o,h,l,c)

if __name__=="__main__":
    main()
