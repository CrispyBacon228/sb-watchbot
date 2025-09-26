from __future__ import annotations
import os, time
from typing import Dict, Tuple

def _yes(s: str) -> bool:
    return str(s).lower() in ("1","true","y","yes")

TICK_SIZE = float(os.getenv("TICK_SIZE","0.25"))
ENTRY_MIN_SEP_SEC   = int(os.getenv("ENTRY_MIN_SEP_SEC","300"))
ENTRY_MIN_SEP_TICKS = int(os.getenv("ENTRY_MIN_SEP_TICKS","8"))
ENTRY_MUTEX_SIDES   = _yes(os.getenv("ENTRY_MUTEX_SIDES","true"))
REQUIRE_NEW_SWEEP   = _yes(os.getenv("REQUIRE_NEW_SWEEP","true"))

class Gate:
    """LIVE gate (wall-clock)."""
    def __init__(self):
        self.last: Dict[str, Tuple[float, float, int]] = {}  # side -> (ts, price, sweep_id)

    def allow(self, side: str, price: float, sweep_id: int | None = None) -> bool:
        now = time.time()
        t,p,sid = self.last.get(side, (0.0, None, None))
        # same sweep? block
        if REQUIRE_NEW_SWEEP and sweep_id is not None and sid is not None and sweep_id == sid:
            return False
        if now - t < ENTRY_MIN_SEP_SEC:
            return False
        if p is not None and abs(price - p) < ENTRY_MIN_SEP_TICKS * TICK_SIZE:
            return False
        if ENTRY_MUTEX_SIDES:
            t_any, p_any, sid_any = self.last.get("ANY",(0.0, None, None))
            if now - t_any < ENTRY_MIN_SEP_SEC:
                return False
        self.last[side] = (now, price, sweep_id if sweep_id is not None else sid)
        self.last["ANY"] = (now, price, sweep_id if sweep_id is not None else sid)
        return True

class GateSim:
    """REPLAY gate (event-time)."""
    def __init__(self):
        self.last: Dict[str, Tuple[float, float, int]] = {}

    def allow_at(self, ts_epoch: float, side: str, price: float, sweep_id: int | None = None) -> bool:
        t,p,sid = self.last.get(side, (0.0, None, None))
        if REQUIRE_NEW_SWEEP and sweep_id is not None and sid is not None and sweep_id == sid:
            return False
        if ts_epoch - t < ENTRY_MIN_SEP_SEC:
            return False
        if p is not None and abs(price - p) < ENTRY_MIN_SEP_TICKS * TICK_SIZE:
            return False
        if ENTRY_MUTEX_SIDES:
            t_any, p_any, sid_any = self.last.get("ANY",(0.0, None, None))
            if ts_epoch - t_any < ENTRY_MIN_SEP_SEC:
                return False
        self.last[side] = (ts_epoch, price, sweep_id if sweep_id is not None else sid)
        self.last["ANY"] = (ts_epoch, price, sweep_id if sweep_id is not None else sid)
        return True
