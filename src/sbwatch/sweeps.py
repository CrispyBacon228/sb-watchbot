from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

@dataclass
class SweepEvent:
    ts: datetime
    level_name: str
    level_price: float
    sweep_price: float
    direction: str  # "bullish" or "bearish"

class SweepDetector:
    def __init__(self, tolerance_ticks: int, tick_size: float, cooldown_min: int):
        self.ticksz = tick_size
        self.tol = tolerance_ticks * tick_size
        self.cooldown = timedelta(minutes=cooldown_min)
        self.last_fired: Dict[str, datetime] = {}

    def _cool(self, key: str, now: datetime) -> bool:
        last = self.last_fired.get(key)
        return True if not last else (now - last) >= self.cooldown

    def check(self, now: datetime, price: float, levels: Dict[str,float]) -> Optional[SweepEvent]:
        for name, lv in levels.items():
            key = f"{name}"
            if not self._cool(key, now): continue
            if "High" in name or name.endswith("PDH"):
                if price >= lv and (price - lv) <= self.tol:
                    self.last_fired[key] = now; return SweepEvent(now, name, lv, price, "bearish")
            if "Low" in name or name.endswith("PDL"):
                if price <= lv and (lv - price) <= self.tol:
                    self.last_fired[key] = now; return SweepEvent(now, name, lv, price, "bullish")
        return None
