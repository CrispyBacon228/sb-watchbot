#!/usr/bin/env python3
import os, sys, json, csv, traceback
from pathlib import Path
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

from src.sbwatch.strategy import SBEngine as _SBEngine
from src.sbwatch import notify as _notify

_real_post = _notify.post_discord
def _wrapped_post(msg: str):
    print(f"[TRACE] post_discord -> {msg.splitlines()[0]}", flush=True)
    return _real_post(msg)
_notify.post_discord = _wrapped_post

def load_levels():
    with open(ROOT/"data"/"levels.json","r") as f:
        return json.load(f)

def iter_csv(path: Path):
    def parse_ts(s):
        s = str(s).strip()
        if s.isdigit() and len(s) >= 12: return int(s)
        if s.isdigit():                    return int(s)*1000
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

def _et(ts_ms:int):
    return datetime.fromtimestamp(ts_ms/1000, tz=ZoneInfo("UTC")).astimezone(ET)

def wrap_engine(eng):
    # log levels snapshot
    lv = getattr(eng, "levels_raw", {})
    L = lv.get("levels") or {}
    am = lv.get("am_box") or {}
    print("[TRACE] levels:",
          {"pdh":L.get("pdh"),"pdl":L.get("pdl"),
           "asia_high":L.get("asia_high"),"asia_low":L.get("asia_low"),
           "london_high":L.get("london_high"),"london_low":L.get("london_low"),
           "am_high":am.get("high"),"am_low":am.get("low")},
          flush=True)

    # wrap the internals
    orig_sweep   = eng._swept_key_level
    orig_disp    = eng._is_displacement
    orig_fvg     = eng._compute_fvg
    orig_entry   = eng._consider_entry_touch
    orig_on_bar  = eng.on_bar

    def w_sweep(i:int):
        s = orig_sweep(i)
        print(f"[GATE] sweep@{i}: {s}", flush=True)
        return s

    def w_disp(i:int, side:str):
        ok = orig_disp(i, side)
        print(f"[GATE] displacement@{i} side={side}: {ok}", flush=True)
        return ok

    def w_fvg(i:int, side:str):
        v = orig_fvg(i, side)
        print(f"[GATE] fvg@{i} side={side}: {v}", flush=True)
        return v

    def w_entry(i:int):
        print(f"[GATE] consider_entry_touch@{i}", flush=True)
        return orig_entry(i)

    def w_on_bar(ts,o,h,l,c):
        dt = _et(ts)
        print(f"[BAR] {dt.strftime('%H:%M:%S')} O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}", flush=True)
        try:
            return orig_on_bar(ts,o,h,l,c)
        except Exception as e:
            print("[ERR] on_bar:", e, flush=True); traceback.print_exc()

    eng._swept_key_level      = w_sweep
    eng._is_displacement      = w_disp
    eng._compute_fvg          = w_fvg
    eng._consider_entry_touch = w_entry
    eng.on_bar                = w_on_bar
    return eng

def main():
    lv = load_levels()
    eng = _SBEngine(lv)
    eng = wrap_engine(eng)

    bar_csv = os.getenv("BAR_CSV")
    src = iter_csv(Path(bar_csv)) if bar_csv else iter_stdin()

    for ts,o,h,l,c in src:
        eng.on_bar(ts,o,h,l,c)

if __name__ == "__main__":
    main()
