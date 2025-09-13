from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Iterable, Dict, Any
from .alerts import TradeAlert

@dataclass
class Bar:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float

def decide_trade_on_bar(bar: Bar) -> Optional[TradeAlert]:
    """
    DEMO RULE:
    - If we get a 'bearish displacement' candle (close < open and high - low > median-ish size),
      emit a SHORT alert with fixed TP/SL ratios.
    Replace this with your SB rules (sweep->displacement->refill, etc).
    """
    body = abs(bar.close - bar.open)
    range_ = (bar.high - bar.low)
    if bar.close < bar.open and range_ > body * 2 and range_ > 5:  # toy heuristic
        entry = bar.close
        stop = bar.high
        risk = stop - entry if stop > entry else 1.0
        tp1 = entry - risk * 1.0
        tp2 = entry - risk * 2.0
        r_mult = (entry - tp2) / risk if risk else 0.0
        return TradeAlert(
            side="SHORT",
            entry=round(entry, 2),
            stop=round(stop, 2),
            tp1=round(tp1, 2),
            tp2=round(tp2, 2),
            r_multiple=round(r_mult, 2),
            basis="Demo Displacement"
        )
    return None
