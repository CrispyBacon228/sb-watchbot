from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from collections import deque
from typing import Optional, Deque, Tuple
from .alerts import TradeAlert
from .execution import Bar, is_displacement, find_fvg, refill_hit
from .sweeps import swept_above, swept_below
from .timebox import in_ny_killzone
from .dedupe import CooldownManager

@dataclass
class SBParams:
    tz: str
    kill_start: str
    kill_end: str
    sweep_ticks: float
    disp_min_ticks: float
    fvg_min_ticks: float
    refill_tol_ticks: float
    tp1_r: float
    tp2_r: float
    stop_buf_ticks: float
    ref_lookback_minutes: int
    require_fvg: bool

class SBEngine:
    def __init__(self, params: SBParams, cd: Optional[CooldownManager]=None):
        self.p = params
        self.prev_bar: Optional[Bar] = None
        self.swept_side: Optional[str] = None
        self.pending_fvg: Optional[Tuple[float,float,str]] = None
        self.basis: str = ""
        self._window: Deque[Bar] = deque()
        self.cd = cd or CooldownManager()

    def _in_kz(self, ts_iso: str) -> bool:
        dt = datetime.fromisoformat(ts_iso.replace("Z","+00:00"))
        return in_ny_killzone(dt, self.p.tz, self.p.kill_start, self.p.kill_end)

    def _update_window(self, bar: Bar) -> None:
        self._window.append(bar)
        while len(self._window) > max(1, self.p.ref_lookback_minutes):
            self._window.popleft()

    def _rolling_refs(self) -> Tuple[Optional[float], Optional[float]]:
        if not self._window:
            return None, None
        highs = [b.high for b in list(self._window)[:-1]] or [self._window[-1].high]
        lows  = [b.low  for b in list(self._window)[:-1]] or [self._window[-1].low]
        return (max(highs), min(lows)) if highs and lows else (None, None)

    def _ok_and_mark(self, side: str, entry: float, stop: float) -> bool:
        band = f"{round(min(entry, stop),1)}-{round(max(entry, stop),1)}"
        key = f"{self.basis}:{side}:{band}"
        if not self.cd.ok(key):
            return False
        self.cd.mark(key)
        return True

    def on_bar(self, bar: Bar, pdh: Optional[float]=None, pdl: Optional[float]=None) -> Optional[TradeAlert]:
        self._update_window(bar)
        if not self._in_kz(bar.ts):
            self.swept_side = None
            self.pending_fvg = None
            self.prev_bar = bar
            return None

        ref_high, ref_low = pdh, pdl
        if ref_high is None or ref_low is None:
            rh, rl = self._rolling_refs()
            ref_high = ref_high if ref_high is not None else rh
            ref_low  = ref_low  if ref_low  is not None else rl

        if ref_high is not None and swept_above(ref_high, bar.high, self.p.sweep_ticks):
            self.swept_side = "SHORT"; self.basis = "ref-high sweep"
        if ref_low is not None and swept_below(ref_low, bar.low, self.p.sweep_ticks):
            self.swept_side = "LONG";  self.basis = "ref-low sweep"

        if self.swept_side and is_displacement(bar, self.p.disp_min_ticks):
            if self.p.require_fvg:
                if self.prev_bar:
                    fvg = find_fvg(self.prev_bar, bar, self.p.fvg_min_ticks)
                    if fvg: self.pending_fvg = fvg
            else:
                if self.swept_side == "SHORT":
                    entry = min(bar.open, bar.close)
                    stop  = bar.high + self.p.stop_buf_ticks
                    risk  = stop - entry
                    tp1, tp2 = entry - self.p.tp1_r*risk, entry - self.p.tp2_r*risk
                else:
                    entry = max(bar.open, bar.close)
                    stop  = bar.low - self.p.stop_buf_ticks
                    risk  = entry - stop
                    tp1, tp2 = entry + self.p.tp1_r*risk, entry + self.p.tp2_r*risk
                if risk > 0 and self._ok_and_mark(self.swept_side, entry, stop):
                    r_mult = abs(tp2 - entry)/risk
                    alert = TradeAlert(
                        side=self.swept_side,
                        entry=round(entry,2),
                        stop=round(stop,2),
                        tp1=round(tp1,2),
                        tp2=round(tp2,2),
                        r_multiple=round(r_mult,2),
                        basis=self.basis or "SB sweep",
                        ts=bar.ts,
                    )
                    self.swept_side = None; self.pending_fvg = None; self.prev_bar = bar
                    return alert

        if self.p.require_fvg and self.pending_fvg:
            upper, lower, side = self.pending_fvg
            if refill_hit(upper, lower, bar, side, self.p.refill_tol_ticks):
                if side == "SHORT":
                    entry = max(lower, min(bar.open, bar.close))
                    stop  = upper + self.p.stop_buf_ticks
                    risk  = stop - entry
                    tp1, tp2 = entry - self.p.tp1_r*risk, entry - self.p.tp2_r*risk
                else:
                    entry = min(upper, max(bar.open, bar.close))
                    stop  = lower - self.p.stop_buf_ticks
                    risk  = entry - stop
                    tp1, tp2 = entry + self.p.tp1_r*risk, entry + self.p.tp2_r*risk
                if risk > 0 and self._ok_and_mark(side, entry, stop):
                    r_mult = abs(tp2 - entry)/risk
                    alert = TradeAlert(
                        side=side,
                        entry=round(entry,2),
                        stop=round(stop,2),
                        tp1=round(tp1,2),
                        tp2=round(tp2,2),
                        r_multiple=round(r_mult,2),
                        basis=self.basis or "SB sweep",
                        ts=bar.ts,
                    )
                    self.swept_side = None; self.pending_fvg = None; self.prev_bar = bar
                    return alert

        self.prev_bar = bar
        return None
