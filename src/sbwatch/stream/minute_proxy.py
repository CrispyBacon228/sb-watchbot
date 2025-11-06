from __future__ import annotations
import csv, os, time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterator, Optional, Any
from sbwatch.live_adapter import iter_live_bars

@dataclass
class Bar:
    ts_ms:int; o:float; h:float; l:float; c:float; v:float

def _num(x, d=0.0):
    try: return float(x)
    except: return float(d)

def _ts_ms(b:Any) -> int:
    ts = getattr(b,'ts_ms', getattr(b,'ts', None))
    if ts is None:
        # upstream gave no timestamp -> use wall clock
        return int(time.time()*1000)
    ts = int(ts)
    if ts < 10_000_000_000:  # seconds -> ms
        ts *= 1000
    return ts

def _wrap(b:Any)->Bar:
    return Bar(
        ts_ms=_ts_ms(b),
        o=_num(getattr(b,'o',getattr(b,'open',None))),
        h=_num(getattr(b,'h',getattr(b,'high',None))),
        l=_num(getattr(b,'l',getattr(b,'low',None))),
        c=_num(getattr(b,'c',getattr(b,'close',None))),
        v=_num(getattr(b,'v',getattr(b,'volume',0.0))),
    )

def _minute_bucket(ts:int)->int:
    return (ts//60000)*60000

def _atomic_write(path:str, rows:list[Bar])->None:
    tmp = path + ".part"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp,"w",newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts_ms","open","high","low","close","volume"])
        for r in rows:
            w.writerow([r.ts_ms, f"{r.o:.2f}", f"{r.h:.2f}", f"{r.l:.2f}", f"{r.c:.2f}", f"{r.v:.0f}"])
    os.replace(tmp, path)

def run_minute_proxy()->None:
    dataset = os.getenv("DATASET","GLBX.MDP3")
    symbol  = os.getenv("SYMBOL","NQ.c.0")
    divisor = float(os.getenv("PRICE_DIVISOR","1e9"))
    out_csv = os.getenv("LIVE_MINUTE_PATH","data/live_minute.csv")
    histmin = int(os.getenv("PROXY_HISTORY_MIN","120"))

    # header so tail -f always works
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv,"w") as fh:
        fh.write("ts_ms,open,high,low,close,volume\n")

    window:Deque[Bar] = deque(maxlen=histmin)
    curr:Optional[int] = None
    agg:Optional[Bar] = None
    last_flush = 0

    for raw in iter_live_bars(dataset=dataset, schema="ohlcv-1s", symbol=symbol, price_divisor=divisor, run_seconds=None):
        b = _wrap(raw)
        mb = _minute_bucket(b.ts_ms)

        if curr is None:
            curr = mb
            agg = Bar(mb, b.o, b.h, b.l, b.c, b.v)
            window.clear(); window.append(agg)
        elif mb != curr:
            curr = mb
            agg = Bar(mb, b.o, b.h, b.l, b.c, b.v)
            window.append(agg)
        else:
            if b.h > agg.h: agg.h = b.h
            if b.l < agg.l: agg.l = b.l
            agg.c = b.c
            agg.v += b.v

        if b.ts_ms - last_flush >= 200:  # ~5 writes/sec
            _atomic_write(out_csv, list(window))
            last_flush = b.ts_ms

def iter_minute_csv_tail(path:str="data/live_minute.csv", poll_ms:int=200)->Iterator[Bar]:
    last_line = None
    header = "ts_ms,open,high,low,close,volume"
    while True:
        try:
            with open(path,"r") as fh:
                lines = fh.read().strip().splitlines()
        except FileNotFoundError:
            time.sleep(poll_ms/1000); continue
        if not lines or lines[0] != header or len(lines) < 2:
            time.sleep(poll_ms/1000); continue
        line = lines[-1]
        if line != last_line:
            last_line = line
            ts,o,h,l,c,v = line.split(",")
            yield Bar(ts_ms=int(ts), o=float(o), h=float(h), l=float(l), c=float(c), v=float(v))
        time.sleep(poll_ms/1000)

if __name__ == "__main__":
    run_minute_proxy()


def iter_minute_csv_tail_fast(path: str = "data/live_minute.csv", poll_ms: int = 200):
    """
    Like iter_minute_csv_tail, but yields a *new* bar every time the last CSV line changes,
    even within the same minute. We keep the minute bucket the same but nudge ts_ms by a
    small +seq (0..999) so downstream 'same ts' de-dupe won't drop it.
    """
    last_line = None
    header = "ts_ms,open,high,low,close,volume"
    base_ts = None
    seq = 0
    while True:
        try:
            with open(path, "r") as fh:
                lines = fh.read().strip().splitlines()
        except FileNotFoundError:
            import time as _t; _t.sleep(poll_ms/1000); continue

        if not lines or lines[0] != header or len(lines) < 2:
            import time as _t; _t.sleep(poll_ms/1000); continue

        line = lines[-1]
        if line != last_line:
            last_line = line
            ts,o,h,l,c,v = line.split(",")
            ts = int(ts)
            # reset seq on minute rollover
            if base_ts is None or (ts // 60000) != (base_ts // 60000):
                base_ts = ts
                seq = 0
            else:
                seq = (seq + 1) % 1000  # stays within same minute
            yield Bar(
                ts_ms = base_ts + seq,   # unique but same minute bucket
                o = float(o), h = float(h), l = float(l), c = float(c), v = float(v)
            )
        import time as _t; _t.sleep(poll_ms/1000)
