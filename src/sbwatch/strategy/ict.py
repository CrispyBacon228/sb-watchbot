# src/sbwatch/strategy/ict.py
from __future__ import annotations

import os
from dataclasses import dataclass
from collections import deque
from typing import List, Optional
from datetime import datetime

@dataclass
class EntrySignal:
    ts: datetime
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    sweep_id: Optional[int] = None

@dataclass
class _FVG:
    side: str
    top: float
    bot: float
    formed_idx: int
    formed_ts: datetime
    sweep_id: Optional[int]

def _ticks(v: float, tick_size: float) -> float:
    return v / tick_size

def _mid(a: float, b: float) -> float:
    return (a + b) * 0.5

class ICTDetector:
    def __init__(self) -> None:
        self.tick_size: float = float(os.getenv("TICK_SIZE", "0.25"))
        self.min_gap_ticks: int   = int(os.getenv("MIN_GAP_TICKS", "2"))
        self.sweep_tol_ticks: int = int(os.getenv("SWEEP_TOL_TICKS", "2"))
        self.swing_lookback: int  = int(os.getenv("SWING_LOOKBACK", "5"))
        self.sb_body_ticks: float = float(os.getenv("SB_BODY_TICKS", "14"))
        self.sb_body_pct: float   = float(os.getenv("SB_BODY_PCT", "0.70"))
        self.revisit_delay_bars: int = int(os.getenv("REVISIT_DELAY_BARS", "2"))
        self.revisit_max_bars: int   = int(os.getenv("REVISIT_MAX_BARS", "8"))
        self.fvg_max_age_min: int = int(os.getenv("FVG_MAX_AGE_MIN", "20"))
        self.rr_tp1: float = float(os.getenv("RR_TP1", "1.0"))
        self.rr_tp2: float = float(os.getenv("RR_TP2", "2.0"))
        self.atr_len: int        = int(os.getenv("ATR_LEN", "14"))
        self.atr_min_ticks: float = float(os.getenv("ATR_MIN_TICKS", "0"))
        self.atr_max_ticks: float = float(os.getenv("ATR_MAX_TICKS", "0"))

        self._bar_idx: int = 0
        self._last_c: Optional[float] = None
        self._o = deque(maxlen=self.swing_lookback + 3)
        self._h = deque(maxlen=self.swing_lookback + 3)
        self._l = deque(maxlen=self.swing_lookback + 3)
        self._c = deque(maxlen=self.swing_lookback + 3)
        self._ts = deque(maxlen=self.swing_lookback + 3)
        self._atr: Optional[float] = None
        self._tr_hist = deque(maxlen=self.atr_len)
        self._last_bull_sweep = None
        self._last_bear_sweep = None
        self._sweep_seq = 0
        self._fvgs: List[_FVG] = []

    def _update_atr(self, h: float, l: float, c: float) -> None:
        if self._last_c is None:
            tr = h - l
        else:
            tr = max(h - l, abs(h - self._last_c), abs(l - self._last_c))
        self._tr_hist.append(tr)
        if self._atr is None:
            if len(self._tr_hist) == self.atr_len:
                self._atr = sum(self._tr_hist) / float(self.atr_len)
        else:
            self._atr = (self._atr * (self.atr_len - 1) + tr) / float(self.atr_len)

    def _atr_ok(self) -> bool:
        if self.atr_min_ticks <= 0 and self.atr_max_ticks <= 0:
            return True
        if self._atr is None:
            return False
        atr_ticks = _ticks(self._atr, self.tick_size)
        lo = self.atr_min_ticks if self.atr_min_ticks > 0 else -1e9
        hi = self.atr_max_ticks if self.atr_max_ticks > 0 else 1e9
        return lo <= atr_ticks <= hi

    def _recent_high(self) -> Optional[float]:
        if len(self._h) < self.swing_lookback + 1:
            return None
        return max(list(self._h)[:-1])

    def _recent_low(self) -> Optional[float]:
        if len(self._l) < self.swing_lookback + 1:
            return None
        return min(list(self._l)[:-1])

    def add_bar(self, ts: datetime, o: float, h: float, l: float, c: float) -> List[EntrySignal]:
        self._bar_idx += 1
        self._o.append(o); self._h.append(h); self._l.append(l); self._c.append(c); self._ts.append(ts)
        self._update_atr(h, l, c)
        self._last_c = c

        out: List[EntrySignal] = []
        tol = self.sweep_tol_ticks * self.tick_size
        rh = self._recent_high()
        rl = self._recent_low()

        if rl is not None and l <= rl - tol and c > rl:
            self._sweep_seq += 1
            self._last_bull_sweep = (self._sweep_seq, float(l), self._bar_idx, ts)
        if rh is not None and h >= rh + tol and c < rh:
            self._sweep_seq += 1
            self._last_bear_sweep = (self._sweep_seq, float(h), self._bar_idx, ts)

        body = abs(c - o)
        rng = max(h - l, 1e-12)
        body_ok = (_ticks(body, self.tick_size) >= self.sb_body_ticks and (body / rng) >= self.sb_body_pct)

        if len(self._o) >= 2 and body_ok and self._atr_ok():
            o_prev, h_prev, l_prev, c_prev, ts_prev = (
                self._o[-2], self._h[-2], self._l[-2], self._c[-2], self._ts[-2]
            )
            gap_ticks = self.min_gap_ticks * self.tick_size
            if c > o and (l > h_prev + gap_ticks):
                sweep = self._last_bull_sweep
                if sweep and (self._bar_idx - sweep[2]) <= 30:
                    self._fvgs.append(_FVG("bull", float(l), float(h_prev), self._bar_idx, ts, sweep[0]))
            if c < o and (h < l_prev - gap_ticks):
                sweep = self._last_bear_sweep
                if sweep and (self._bar_idx - sweep[2]) <= 30:
                    self._fvgs.append(_FVG("bear", float(l_prev), float(h), self._bar_idx, ts, sweep[0]))

        if self._fvgs:
            keep: List[_FVG] = []
            for f in self._fvgs:
                age = self._bar_idx - f.formed_idx
                valid_age = (age >= self.revisit_delay_bars) and (age <= self.revisit_max_bars)
                if age > max(self.revisit_max_bars, self.fvg_max_age_min):
                    continue
                touched = (l <= f.top) and (h >= f.bot)
                if valid_age and touched:
                    entry = _mid(f.top, f.bot)
                    if f.side == "bull":
                        stop = min(f.bot, (self._last_bull_sweep[1] if self._last_bull_sweep else f.bot)) - self.tick_size
                        risk = max(entry - stop, self.tick_size)
                        tp1 = entry + self.rr_tp1 * risk
                        tp2 = entry + self.rr_tp2 * risk
                        out.append(EntrySignal(ts, "bull", entry, stop, tp1, tp2, f.sweep_id))
                    else:
                        stop = max(f.top, (self._last_bear_sweep[1] if self._last_bear_sweep else f.top)) + self.tick_size
                        risk = max(stop - entry, self.tick_size)
                        tp1 = entry - self.rr_tp1 * risk
                        tp2 = entry - self.rr_tp2 * risk
                        out.append(EntrySignal(ts, "bear", entry, stop, tp1, tp2, f.sweep_id))
                    continue
                else:
                    keep.append(f)
            self._fvgs = keep

        return out


# =========================
# Silver Bullet monkey-patch
# =========================
from types import SimpleNamespace
from collections import deque
import os

try:
    _SB_OLD_INIT = ICTDetector.__init__
except Exception:
    _SB_OLD_INIT = None

def _SB_init(self, *args, **kwargs):
    # Call original __init__ if present
    if _SB_OLD_INIT:
        try:
            _SB_OLD_INIT(self, *args, **kwargs)
        except Exception:
            pass
    # Ensure minimal state for SB logic
    if not hasattr(self, "_bars"):   self._bars   = deque(maxlen=3)   # (ts,o,h,l,c)
    if not hasattr(self, "_hi_buf"): self._hi_buf = deque(maxlen=200) # highs buffer
    if not hasattr(self, "_lo_buf"): self._lo_buf = deque(maxlen=200) # lows buffer

def _SB_add_bar(self, ts, o, h, l, c):
    """
    ICT Silver Bullet (AM):
      1) Sweep prior H/L within lookback
      2) Displacement candle away from sweep (min body)
      3) 3-candle FVG
      4) Entry at 50% of FVG (mean threshold). Stop beyond FVG (+pad). TP1=1R, TP2=2R
    Returns: list[SimpleNamespace(side, entry, stop, tp1, tp2, sweep_id)]
    """
    # Tunables (env overrides)
    TICK      = float(os.getenv("TICK_SIZE", "0.25"))
    PAD_TICKS = int(os.getenv("SB_STOP_PAD_TICKS", "2"))
    MIN_FVG   = int(os.getenv("SB_MIN_FVG_TICKS", "6")) * TICK
    MIN_BODY  = int(os.getenv("SB_MIN_BODY_TICKS", "8")) * TICK
    SWEEP_LB  = int(os.getenv("SB_SWEEP_LOOKBACK", "20"))
    R_MULT1   = float(os.getenv("RR_TP1", "1.0"))
    R_MULT2   = float(os.getenv("RR_TP2", "2.0"))

    # Update rolling buffers
    self._bars.append((ts, o, h, l, c))
    self._hi_buf.append(h)
    self._lo_buf.append(l)

    out = []
    if len(self._bars) < 3:
        return out

    (ts1,o1,h1,l1,c1), (ts2,o2,h2,l2,c2), (ts3,o3,h3,l3,c3) = self._bars[0], self._bars[1], self._bars[2]

    # Sweep detection (use prior history excluding current)
    if len(self._hi_buf) < 5 or len(self._lo_buf) < 5:
        return out
    prev_high = max(list(self._hi_buf)[:-1])
    prev_low  = min(list(self._lo_buf)[:-1])

    swept_high = h3 > prev_high + 0.5*TICK   # swept liquidity above
    swept_low  = l3 < prev_low  - 0.5*TICK   # swept liquidity below

    # Displacement candle (body away from sweep side)
    body3   = abs(c3 - o3)
    bear_ok = swept_high and (c3 < o3) and (body3 >= MIN_BODY)
    bull_ok = swept_low  and (c3 > o3) and (body3 >= MIN_BODY)

    # 3-candle FVG checks: c1,c2,c3 = bars 1,2,3
    bull_fvg = l3 > h1         # gap up
    bear_fvg = h3 < l1         # gap down

    # Bullish: swept lows + up displacement + bull FVG -> buy at MT of FVG
    if bull_ok and bull_fvg:
        gap_low, gap_high = h1, l3
        gap = gap_high - gap_low
        if gap >= MIN_FVG:
            mt   = (gap_high + gap_low) / 2.0
            stop = gap_low - PAD_TICKS*TICK
            risk = mt - stop
            if risk > 0:
                tp1 = mt + R_MULT1*risk
                tp2 = mt + R_MULT2*risk
                out.append(SimpleNamespace(
                    side="bull", entry=mt, stop=stop, tp1=tp1, tp2=tp2,
                    sweep_id=f"sweep_lo@{ts3}"
                ))
            return out   # one signal per bar

    # Bearish: swept highs + down displacement + bear FVG -> sell at MT of FVG
    if bear_ok and bear_fvg:
        gap_high, gap_low = l1, h3
        gap = gap_high - gap_low
        if gap >= MIN_FVG:
            mt   = (gap_high + gap_low) / 2.0
            stop = gap_high + PAD_TICKS*TICK
            risk = stop - mt
            if risk > 0:
                tp1 = mt - R_MULT1*risk
                tp2 = mt - R_MULT2*risk
                out.append(SimpleNamespace(
                    side="bear", entry=mt, stop=stop, tp1=tp1, tp2=tp2,
                    sweep_id=f"sweep_hi@{ts3}"
                ))
            return out

    return out

# Activate monkey-patch
ICTDetector.__init__ = _SB_init
ICTDetector.add_bar  = _SB_add_bar
# =========================


# =========================
# Silver Bullet monkey-patch
# =========================
from types import SimpleNamespace
from collections import deque
import os

try:
    _SB_OLD_INIT = ICTDetector.__init__
except Exception:
    _SB_OLD_INIT = None

def _SB_init(self, *args, **kwargs):
    # Call original __init__ if present
    if _SB_OLD_INIT:
        try:
            _SB_OLD_INIT(self, *args, **kwargs)
        except Exception:
            pass
    # Ensure minimal state for SB logic
    if not hasattr(self, "_bars"):   self._bars   = deque(maxlen=3)   # (ts,o,h,l,c)
    if not hasattr(self, "_hi_buf"): self._hi_buf = deque(maxlen=200) # highs buffer
    if not hasattr(self, "_lo_buf"): self._lo_buf = deque(maxlen=200) # lows buffer

def _SB_add_bar(self, ts, o, h, l, c):
    """
    ICT Silver Bullet (AM):
      1) Sweep prior H/L within lookback
      2) Displacement candle away from sweep (min body)
      3) 3-candle FVG
      4) Entry at 50% of FVG (mean threshold). Stop beyond FVG (+pad). TP1=1R, TP2=2R
    Returns: list[SimpleNamespace(side, entry, stop, tp1, tp2, sweep_id)]
    """
    # Tunables (env overrides)
    TICK      = float(os.getenv("TICK_SIZE", "0.25"))
    PAD_TICKS = int(os.getenv("SB_STOP_PAD_TICKS", "2"))
    MIN_FVG   = int(os.getenv("SB_MIN_FVG_TICKS", "6")) * TICK
    MIN_BODY  = int(os.getenv("SB_MIN_BODY_TICKS", "8")) * TICK
    SWEEP_LB  = int(os.getenv("SB_SWEEP_LOOKBACK", "20"))
    R_MULT1   = float(os.getenv("RR_TP1", "1.0"))
    R_MULT2   = float(os.getenv("RR_TP2", "2.0"))

    # Update rolling buffers
    self._bars.append((ts, o, h, l, c))
    self._hi_buf.append(h)
    self._lo_buf.append(l)

    out = []
    if len(self._bars) < 3:
        return out

    (ts1,o1,h1,l1,c1), (ts2,o2,h2,l2,c2), (ts3,o3,h3,l3,c3) = self._bars[0], self._bars[1], self._bars[2]

    # Sweep detection (use prior history excluding current)
    if len(self._hi_buf) < 5 or len(self._lo_buf) < 5:
        return out
    prev_high = max(list(self._hi_buf)[:-1])
    prev_low  = min(list(self._lo_buf)[:-1])

    swept_high = h3 > prev_high + 0.5*TICK   # swept liquidity above
    swept_low  = l3 < prev_low  - 0.5*TICK   # swept liquidity below

    # Displacement candle (body away from sweep side)
    body3   = abs(c3 - o3)
    bear_ok = swept_high and (c3 < o3) and (body3 >= MIN_BODY)
    bull_ok = swept_low  and (c3 > o3) and (body3 >= MIN_BODY)

    # 3-candle FVG checks: c1,c2,c3 = bars 1,2,3
    bull_fvg = l3 > h1         # gap up
    bear_fvg = h3 < l1         # gap down

    # Bullish: swept lows + up displacement + bull FVG -> buy at MT of FVG
    if bull_ok and bull_fvg:
        gap_low, gap_high = h1, l3
        gap = gap_high - gap_low
        if gap >= MIN_FVG:
            mt   = (gap_high + gap_low) / 2.0
            stop = gap_low - PAD_TICKS*TICK
            risk = mt - stop
            if risk > 0:
                tp1 = mt + R_MULT1*risk
                tp2 = mt + R_MULT2*risk
                out.append(SimpleNamespace(
                    side="bull", entry=mt, stop=stop, tp1=tp1, tp2=tp2,
                    sweep_id=f"sweep_lo@{ts3}"
                ))
            return out   # one signal per bar

    # Bearish: swept highs + down displacement + bear FVG -> sell at MT of FVG
    if bear_ok and bear_fvg:
        gap_high, gap_low = l1, h3
        gap = gap_high - gap_low
        if gap >= MIN_FVG:
            mt   = (gap_high + gap_low) / 2.0
            stop = gap_high + PAD_TICKS*TICK
            risk = stop - mt
            if risk > 0:
                tp1 = mt - R_MULT1*risk
                tp2 = mt - R_MULT2*risk
                out.append(SimpleNamespace(
                    side="bear", entry=mt, stop=stop, tp1=tp1, tp2=tp2,
                    sweep_id=f"sweep_hi@{ts3}"
                ))
            return out

    return out

# Activate monkey-patch
ICTDetector.__init__ = _SB_init
ICTDetector.add_bar  = _SB_add_bar
# =========================
