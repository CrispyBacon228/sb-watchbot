from __future__ import annotations
import json, os, datetime
from zoneinfo import ZoneInfo

LEVELS_FP = "/opt/sb-watchbot/data/levels.json"
ET = ZoneInfo("America/New_York")
_DIVISOR = 1e7  # Databento prices are integers; divide to get human price

def load_levels_for_today(divide: float = _DIVISOR) -> dict:
    """Read levels.json and return today's levels with prices divided."""
    key = datetime.datetime.now(ET).strftime("%Y-%m-%d")
    if not os.path.exists(LEVELS_FP):
        return {}
    try:
        with open(LEVELS_FP) as f:
            data = json.load(f)
        raw = data.get(key, {})
    except Exception:
        return {}

    out = {}
    for sess in ("asia", "london", "prev_day"):
        s = raw.get(sess, {})
        out[sess] = {
            "high": round((s.get("high") or 0) / divide, 2),
            "low":  round((s.get("low")  or 0) / divide, 2),
            "start": s.get("start"),
            "end":   s.get("end"),
        }
    return out
