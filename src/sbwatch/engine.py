from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict
from .timebox import is_pre10_trade_window, is_sb_window, is_after_11, is_after_london_to_10
from .execution import ExecutionFilters, CandleBuilder, DisplacementSignal

@dataclass
class TradeIdea:
    kind: str; side: str; level_name: str
    entry: Optional[float]; stop: Optional[float]; tp1: Optional[float]; tp2: Optional[float]; R: Optional[float]
    when_et: datetime; note: str = ""

class Engine:
    def __init__(self, tick_size: float, stop_buffer_ticks: int, settings):
        self.ts = tick_size; self.stopbuf = stop_buffer_ticks * tick_size; self.settings = settings
        ex = settings.execution
        self.cb = CandleBuilder()
        self.filters = ExecutionFilters(
            k_body=ex.get("k_body_multiple",1.5),
            n_body=ex.get("n_body_lookback",10),
            require_fvg=ex.get("require_fvg_on_displacement", True),
            entry_on_refill=ex.get("entry_on_fvg_refill", True),
        )
        self.entry_basis = ex.get("entry_basis","last")

    def on_tick_for_candles(self, ts: datetime, price: float): self.cb.add_tick(ts, price)

    def risk_calc(self, direction: str, entry: float, swept_level: float):
        if direction == "bearish":
            stop = max(entry, swept_level + self.stopbuf); R = abs(entry - stop); tp1 = entry - R; tp2 = entry - 2*R
        else:
            stop = min(entry, swept_level - self.stopbuf); R = abs(entry - stop); tp1 = entry + R; tp2 = entry + 2*R
        return stop, tp1, tp2, R

    def build_levels_map(self, day_levels: Dict[str,Dict]) -> Dict[str,float]:
        return {
            "Asia High":  float(day_levels["asia"]["high"]),
            "Asia Low":   float(day_levels["asia"]["low"]),
            "London High":float(day_levels["london"]["high"]),
            "London Low": float(day_levels["london"]["low"]),
            "PDH":        float(day_levels["prev_day"]["high"]),
            "PDL":        float(day_levels["prev_day"]["low"]),
        }

    def decide(self, now: datetime, sweep_direction: str, level_name: str, level_price: float, last_price: float) -> Optional[TradeIdea]:
        if is_after_11(now): return None
        if is_after_london_to_10(now):
            side = "SHORT" if sweep_direction=="bearish" else "LONG"
            return TradeIdea(kind="INFO", side=f"BIAS {side}", level_name=level_name,
                             entry=None, stop=None, tp1=None, tp2=None, R=None, when_et=now,
                             note="Sweep detected (after London → 10:00).")
        is_pre10 = is_pre10_trade_window(now); is_sb = is_sb_window(now)
        sig: Optional[DisplacementSignal] = self.filters.detect_displacement_and_fvg(self.cb)
        if self.settings.execution.get("require_displacement_candle", True) and not sig:
            if is_pre10 or is_sb: return None
        side = "SHORT" if sweep_direction=="bearish" else "LONG"
        if sig and ((sig.direction=="short" and side!="SHORT") or (sig.direction=="long" and side!="LONG")): return None
        entry_price = last_price
        if sig:
            epx = self.filters.entry_from_signal(sig, last_price)
            if self.settings.execution.get("entry_on_fvg_refill", True) and epx is None: return None
            if epx is not None: entry_price = epx
        stop, tp1, tp2, R = self.risk_calc(sweep_direction, entry_price, level_price)
        kind = "SB" if is_sb else ("TRADE" if is_pre10 else "INFO")
        if kind == "INFO": return None
        return TradeIdea(kind=kind, side=side, level_name=level_name,
                         entry=round(entry_price,2), stop=round(stop,2),
                         tp1=round(tp1,2), tp2=round(tp2,2), R=round(R,2), when_et=now)
