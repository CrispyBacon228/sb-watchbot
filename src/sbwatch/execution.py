from __future__ import annotations
from typing import Deque, Optional
from collections import deque
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Candle:
    t_open: datetime; open: float; high: float; low: float; close: float

class CandleBuilder:
    def __init__(self):
        self.current: Optional[Candle] = None; self.buffer: Deque[Candle] = deque(maxlen=50)
    def add_tick(self, ts: datetime, price: float) -> Optional[Candle]:
        minute_key = ts.replace(second=0, microsecond=0)
        if not self.current or self.current.t_open != minute_key:
            if self.current: self.buffer.append(self.current)
            self.current = Candle(minute_key, price, price, price, price); return self.current
        c = self.current; c.high = max(c.high, price); c.low = min(c.low, price); c.close = price; return None

def median_body(bodies):
    arr = sorted(bodies); n = len(arr)
    if n == 0: return 0.0
    mid = n//2; return arr[mid] if n%2 else 0.5*(arr[mid-1]+arr[mid])

@dataclass
class DisplacementSignal:
    direction: str; fvg_top: float; fvg_bot: float; anchor_close: float; formed_at: datetime

class ExecutionFilters:
    def __init__(self, k_body: float, n_body: int, require_fvg: bool, entry_on_refill: bool):
        self.k=k_body; self.n=n_body; self.require_fvg=require_fvg; self.entry_on_refill=entry_on_refill

    def detect_displacement_and_fvg(self, cb: CandleBuilder) -> Optional[DisplacementSignal]:
        if len(cb.buffer) < 3: return None
        c1, c2, c3 = cb.buffer[-3], cb.buffer[-2], cb.buffer[-1]
        bodies = [abs(c.close - c.open) for c in list(cb.buffer)[-self.n:]]
        med = median_body(bodies)
        if med == 0: return None
        if abs(c3.close - c3.open) < self.k * med: return None
        short_fvg = c1.high < c3.low
        long_fvg  = c1.low  > c3.high
        if self.require_fvg and not (short_fvg or long_fvg): return None
        if short_fvg:  return DisplacementSignal("short", fvg_top=c1.high, fvg_bot=c3.low, anchor_close=c3.close, formed_at=c3.t_open)
        if long_fvg:   return DisplacementSignal("long",  fvg_top=c3.high, fvg_bot=c1.low, anchor_close=c3.close, formed_at=c3.t_open)
        return None

    def entry_from_signal(self, sig: DisplacementSignal, last_price: float) -> Optional[float]:
        if not self.entry_on_refill: return last_price
        if sig.direction == "short":
            return last_price if sig.fvg_bot <= last_price <= sig.fvg_top else None
        return last_price if sig.fvg_top <= last_price <= sig.fvg_bot else None
