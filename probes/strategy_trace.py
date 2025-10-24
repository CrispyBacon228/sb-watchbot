#!/usr/bin/env python3
import os, sys, json, csv, traceback
from pathlib import Path
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

# Import your actual modules
from src.sbwatch import notify as _notify
from src.sbwatch.strategy import SBEngine as _SBEngine

# --- Monkey-patch notify to also print to console ---
_real_post = _notify.post_discord
def _wrapped_post(msg: str):
    print(f"[TRACE] post_discord: {msg.splitlines()[0]}", flush=True)
    return _real_post(msg)
_notify.post_discord = _wrapped_post

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

# Wrap SBEngine.on_bar to log reasons when nothing triggers
def wrap_engine(eng):
    orig = eng.on_bar
    ws = getattr(eng, "window_start", None)
    we = getattr(eng, "window_end", None)

    # best-effort: extract levels the engine might use
    lv = getattr(eng, "levels_raw", None)
    if isinstance(lv, dict):
        L = lv.get("levels") or {}
        am = lv.get("am_box") or {}
        print("[TRACE] levels snapshot:",
              { "pdh": L.get("pdh"), "pdl": L.get("pdl"),
                "asia_high": L.get("asia_high"), "asia_low": L.get("asia_low"),
                "london_high": L.get("london_high"), "london_low": L.get("london_low"),
                "am_high": am.get("high"), "am_low": am.get("low") },
              flush=True)

    def _et(ts_ms:int):
        return datetime.fromtimestamp(ts_ms/1000, tz=ZoneInfo("UTC")).astimezone(ET)

    def wrapped(ts_ms, o, h, l, c):
        dt_et = _et(ts_ms)
        in_window = True
        if ws and we:
            t = dt_et.timetz().replace(tzinfo=None)
            in_window = (ws <= t < we)

        print(f"[TRACE] bar {dt_et.strftime('%H:%M:%S')} ET  O:{o:.2f} H:{h:.2f} L:{l:.2f} C:{c:.2f}  "
              f"window={'YES' if in_window else 'NO'}", flush=True)

        try:
            return orig(ts_ms, o, h, l, c)
        except Exception as e:
            print("[TRACE] on_bar exception:", repr(e), flush=True)
            traceback.print_exc()

    eng.on_bar = wrapped
    return eng

def main():
    levels = load_levels()
    eng = _SBEngine(levels)
    eng = wrap_engine(eng)

    bar_csv = os.getenv("BAR_CSV")
    src = iter_csv(Path(bar_csv)) if bar_csv else iter_stdin()

    for ts,o,h,l,c in src:
        eng.on_bar(ts,o,h,l,c)

if __name__ == "__main__":
    main()
