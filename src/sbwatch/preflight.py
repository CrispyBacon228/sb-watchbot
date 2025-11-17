from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple
import math

@dataclass
class PreflightResult:
    status: str        # "CLEAN", "CHOP", "UNKNOWN"
    bias: str          # "BULL", "BEAR", "NEUTRAL"
    score: float       # rough 0-1 cleanliness score
    reasons: List[str]

def _body(o: float, c: float) -> float:
    return abs(c - o)

def _range(h: float, l: float) -> float:
    return max(0.0, h - l)

def analyze_bars(bars: List[Dict]) -> PreflightResult:
    """
    bars: list of dicts with keys: ts_ms, o, h, l, c
    Uses last ~30 minutes of data to classify the session.
    """
    if len(bars) < 10:
        return PreflightResult(
            status="UNKNOWN",
            bias="NEUTRAL",
            score=0.0,
            reasons=["Not enough bars to judge (need at least 10)."],
        )

    # --- basic aggregates ---
    closes = [b["c"] for b in bars]
    highs  = [b["h"] for b in bars]
    lows   = [b["l"] for b in bars]
    opens  = [b["o"] for b in bars]

    total_range = max(highs) - min(lows)
    ranges = [_range(h, l) for h, l in zip(highs, lows)]
    bodies = [_body(o, c) for o, c in zip(opens, closes)]
    avg_range = sum(ranges) / len(ranges)
    avg_body = sum(bodies) / len(bodies)

    # net move & bias
    net_move = closes[-1] - closes[0]
    bias = "BULL" if net_move > 0 else "BEAR" if net_move < 0 else "NEUTRAL"

    # --- displacement candles (strong pushes) ---
    strong_pushes = 0
    for o, h, l, c in zip(opens, highs, lows, closes):
        r = _range(h, l)
        b = _body(o, c)
        if r <= 0:
            continue
        disp = b / r
        # require decent size and body dominance
        if b >= max(8.0, 0.75 * avg_range) and disp >= 0.6:
            strong_pushes += 1

    # --- chop metrics: flip-flops & inside bars ---
    dir_signs = []
    for o, c in zip(opens, closes):
        if c > o:
            dir_signs.append(1)
        elif c < o:
            dir_signs.append(-1)
        else:
            dir_signs.append(0)

    flips = 0
    for a, b in zip(dir_signs, dir_signs[1:]):
        if a * b < 0:  # changed from up to down or down to up
            flips += 1
    flip_ratio = flips / max(1, len(dir_signs) - 1)

    inside_bars = 0
    for (ph, pl, h, l) in zip(highs, lows, highs[1:], lows[1:]):
        if h <= ph and l >= pl:
            inside_bars += 1
    inside_ratio = inside_bars / max(1, len(bars) - 1)

    reasons: List[str] = []

    # --- evaluate cleanliness ---
    clean_score = 0.0

    # displacement contribution
    if strong_pushes >= 2:
        clean_score += 0.4
        reasons.append(f"{strong_pushes} strong displacement pushes.")
    elif strong_pushes == 1:
        clean_score += 0.2
        reasons.append("Only 1 strong displacement push.")
    else:
        reasons.append("No strong displacement candles (weak conviction).")

    # directionality
    if total_range > 0:
        directional_efficiency = abs(net_move) / total_range
    else:
        directional_efficiency = 0.0

    if directional_efficiency >= 0.5:
        clean_score += 0.3
        reasons.append(f"Directional move is strong (efficiency ~{directional_efficiency:.2f}).")
    elif directional_efficiency >= 0.3:
        clean_score += 0.15
        reasons.append(f"Directional move is moderate (efficiency ~{directional_efficiency:.2f}).")
    else:
        reasons.append(f"Directional move is weak (efficiency ~{directional_efficiency:.2f}).")

    # chop penalties
    if flip_ratio <= 0.3:
        clean_score += 0.15
        reasons.append(f"Low flip-flop (flip ratio ~{flip_ratio:.2f}).")
    elif flip_ratio <= 0.5:
        clean_score += 0.05
        reasons.append(f"Moderate flip-flop (flip ratio ~{flip_ratio:.2f}).")
    else:
        clean_score -= 0.2
        reasons.append(f"High flip-flop (flip ratio ~{flip_ratio:.2f}) — choppy.")

    if inside_ratio <= 0.2:
        clean_score += 0.15
        reasons.append(f"Few inside bars (inside ratio ~{inside_ratio:.2f}).")
    elif inside_ratio <= 0.4:
        clean_score += 0.05
        reasons.append(f"Some inside bars (inside ratio ~{inside_ratio:.2f}).")
    else:
        clean_score -= 0.1
        reasons.append(f"Many inside bars (inside ratio ~{inside_ratio:.2f}) — compression.")

    # volatility sanity: if total_range is tiny, that's bad too
    if total_range < 2 * avg_range:
        clean_score -= 0.15
        reasons.append("Overall range is small relative to average bar size (likely low energy).")

    # clamp score to 0..1
    clean_score = max(0.0, min(1.0, clean_score))

    if clean_score >= 0.6:
        status = "CLEAN"
    elif clean_score >= 0.4:
        status = "MIXED"
    else:
        status = "CHOP"

    return PreflightResult(
        status=status,
        bias=bias,
        score=clean_score,
        reasons=reasons,
    )
