from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class DayLevels:
    date: str
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    london_high: Optional[float] = None
    london_low: Optional[float] = None

    def as_dict(self) -> Dict[str, float | None]:
        return vars(self)
