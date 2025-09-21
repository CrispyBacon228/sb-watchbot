from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Deque, Tuple
from collections import deque

# --- core types this file needs ---
# Keep these light so this file can be imported in isolation
@dataclass
class SBParams:
    tz: str
    kill_start: str
    kill_end: str
    sweep_ticks: int
    disp_min_ticks: int
    fvg_min_ticks: int
    refill_tol_ticks: int
    tp1_r: float
    tp2_r: float
    stop_buf_ticks: int
    ref_lookback_minutes: int
    require_fvg: bool

@dataclass
class Bar:
    ts: str
    open: float
    high: float
    low: float
    close: float

# Minimal cooldown manager stub; your real one can be wired back
class CooldownManager:
    def __init__(self) -> None:
        self._seen: set[str] = set()

# DayLevels as produced by build_levels()
@dataclass
class DayLevels:
    date: str
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    london_high: Optional[float] = None
    london_low: Optional[float] = None

# -------- ENGINE --------
class SBEngine:
    """
    Strategy engine. `levels` is optional; when provided it lets the engine
    use PDH/PDL and Asia/London H/L without re-fetching.
    """

    def __init__(self, params: SBParams, cd: Optional[CooldownManager]=None, levels: Optional[DayLevels]=None):
        self.p = params
        self.levels: Optional[DayLevels] = levels     # <— this is the new line that matters
        self.prev_bar: Optional[Bar] = None
        self.swept_side: Optional[str] = None
        self.pending_fvg: Optional[Tuple[float,float,str]] = None
        self.basis: str = ""
        self._window: Deque[Bar] = deque()
        self.cd = cd or CooldownManager()

    # Keep your existing logic below … here are thin stubs so import works
    def on_bar(self, bar: Bar) -> Optional[dict]:
        # your real logic goes here; levels are available at self.levels
        return None
