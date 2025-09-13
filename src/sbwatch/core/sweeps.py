from __future__ import annotations

def swept_above(level: float, high: float, tol: float) -> bool:
    return high >= level and (high - level) <= tol

def swept_below(level: float, low: float, tol: float) -> bool:
    return low <= level and (level - low) <= tol
