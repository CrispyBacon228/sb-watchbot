from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json

@dataclass
class DayLevels:
    date_et: str
    pdh: float
    pdl: float
    asia_high: float
    asia_low: float
    london_high: float
    london_low: float

def load_levels(path: str | Path) -> DayLevels:
    obj = json.loads(Path(path).read_text())
    # legacy coercions if older keys exist
    if "pd1" in obj and "pdh" not in obj: obj["pdh"] = obj.pop("pd1")
    return DayLevels(**obj)

def save_levels(path: str | Path, lv: DayLevels) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(lv), indent=2))
    tmp.replace(p)  # atomic write
