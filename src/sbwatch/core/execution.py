from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class Bar:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float

def is_displacement(bar: Bar, min_ticks: float) -> bool:
    rng = bar.high - bar.low
    body = abs(bar.close - bar.open)
    return rng >= min_ticks and rng >= body * 2

def find_fvg(prev: Bar, curr: Bar, min_gap: float) -> Optional[Tuple[float, float, str]]:
    """
    Returns (upper, lower, side) of FVG box if exists.
    - bearish FVG: prev.low > curr.high => gap between curr.high .. prev.low
    - bullish FVG: prev.high < curr.low => gap between prev.high .. curr.low
    """
    if prev.low - curr.high >= min_gap:
        return (curr.high, prev.low, "SHORT")  # bearish FVG (sell on refill up)
    if curr.low - prev.high >= min_gap:
        return (prev.high, curr.low, "LONG")   # bullish FVG (buy on refill down)
    return None

def refill_hit(fvg_upper: float, fvg_lower: float, bar: Bar, side: str, tol: float) -> bool:
    if side == "SHORT":
        # price refills upwards into FVG and trades back down (touch within tol)
        return bar.high >= (fvg_upper - tol) and bar.close < bar.open
    else:
        return bar.low <= (fvg_lower + tol) and bar.close > bar.open
