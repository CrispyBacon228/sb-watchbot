#!/usr/bin/env python3
import os, csv, json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

from src.sbwatch.strategy import SBEngine as _SBEngine

def load_levels():
    with open(ROOT/"data"/"levels.json","r") as f:
        return json.load(f)

def iter_csv(path: Path):
    def ts(s):
        s=str(s).strip()
        if s.isdigit() and len(s)>=12: return int(s)
        if s.isdigit(): return int(s)*1000
        from datetime import datetime, timezone
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp()*1000)
    with open(path,"r",newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            yield ts(row["ts"]), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])

from dataclasses import dataclass
@dataclass
class Bar: ts_ms:int; o:float; h:float; l:float; c:float

def main():
    lv=load_levels()
    eng=_SBEngine(lv)

    # Monkey-patch ONLY the displacement method to print internals
    orig=eng._is_displacement
    def dbg(i:int, side:str)->bool:
        b=eng.bars[i]
        import math
        # compute med exactly like engine
        med=max(eng._median_body(), 1e-6)
        body=abs(b.c-b.o)
        last_hi=eng.swings.last_high
        last_lo=eng.swings.last_low
        takes = (b.h>last_hi) if side=="long" else (b.l<last_lo)
        dirn  = (b.c>b.o)     if side=="long" else (b.c<b.o)
        mult=float(os.getenv("SB_BODY_MULT","1.6"))
        thresh=mult*med
        ok=orig(i,side)
        ts=datetime.fromtimestamp(b.ts_ms/1000, tz=ET).strftime("%H:%M:%S")
        print(f"[DISP] i={i} {ts} side={side} "
              f"last_hi={last_hi:.5f} last_lo={last_lo:.5f} "
              f"h={b.h:.5f} l={b.l:.5f} o={b.o:.5f} c={b.c:.5f} "
              f"dir={dirn} takes={takes} body={body:.5f} med={med:.5f} mult={mult} thr={thresh:.5f} -> {ok}",
              flush=True)
        return ok
    eng._is_displacement=dbg

    # small wrapper to force levels to print once
    print("[TRACE] levels:", {k:lv.get(k) or (lv.get("levels") or {}).get(k) for k in ["pdh","pdl","asia_high","asia_low","london_high","london_low"]})

    bar_csv=os.getenv("BAR_CSV")
    for ts,o,h,l,c in iter_csv(Path(bar_csv)):
        # reproduce SBEngine.on_bar path up to displacement
        # let engine run normally so sweep etc. happen
        eng.on_bar(ts,o,h,l,c)

if __name__=="__main__":
    main()
