from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class PreflightResult:
    status: str        # "CLEAN", "MIXED", "CHOP", "UNKNOWN"
    bias: str          # "BULL", "BEAR", "NEUTRAL"
    score: float       # 0..1 cleanliness score
    reasons: List[str]

    # new fields
    long_ok: bool
    short_ok: bool
    directional_efficiency: float  # |net_move| / total_range
    net_move: float
    total_range: float
    strong_pushes: int


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(0.0, h - l)


def analyze_bars(bars: List[Dict]) -> PreflightResult:
    """
    bars: list of dicts with keys: ts_ms, o, h, l, c
    Uses last ~30 minutes of data to classify the session and
    determine if LONGS / SHORTS are aligned with bias.
    """
    if len(bars) < 10:
        return PreflightResult(
            status="UNKNOWN",
            bias="NEUTRAL",
            score=0.0,
            reasons=["Not enough bars to judge (need at least 10)."],
            long_ok=False,
            short_ok=False,
            directional_efficiency=0.0,
            net_move=0.0,
            total_range=0.0,
            strong_pushes=0,
        )

    closes = [b["c"] for b in bars]
    highs = [b["h"] for b in bars]
    lows = [b["l"] for b in bars]
    opens = [b["o"] for b in bars]

    total_range = max(highs) - min(lows)
    ranges = [_range(h, l) for h, l in zip(highs, lows)]
    bodies = [_body(o, c) for o, c in zip(opens, closes)]
    avg_range = sum(ranges) / len(ranges) if ranges else 0.0
    avg_body = sum(bodies) / len(bodies) if bodies else 0.0

    net_move = closes[-1] - closes[0]
    if net_move > 0:
        bias = "BULL"
    elif net_move < 0:
        bias = "BEAR"
    else:
        bias = "NEUTRAL"

    if total_range > 0:
        directional_efficiency = abs(net_move) / total_range
    else:
        directional_efficiency = 0.0

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
        if a * b < 0:
            flips += 1
    flip_ratio = flips / max(1, len(dir_signs) - 1)

    inside_bars = 0
    for (ph, pl, h, l) in zip(highs, lows, highs[1:], lows[1:]):
        if h <= ph and l >= pl:
            inside_bars += 1
    inside_ratio = inside_bars / max(1, len(bars) - 1)

    reasons: List[str] = []
    clean_score = 0.0

    # displacement contribution
    if strong_pushes >= 3:
        clean_score += 0.45
        reasons.append(f"{strong_pushes} strong displacement pushes.")
    elif strong_pushes >= 1:
        clean_score += 0.25
        reasons.append(f"{strong_pushes} strong displacement push(es).")
    else:
        reasons.append("No strong displacement candles (weak conviction).")

    # directionality
    if directional_efficiency >= 0.6:
        clean_score += 0.3
        reasons.append(f"Directional move is strong (efficiency ~{directional_efficiency:.2f}).")
    elif directional_efficiency >= 0.35:
        clean_score += 0.15
        reasons.append(f"Directional move is moderate (efficiency ~{directional_efficiency:.2f}).")
    else:
        reasons.append(f"Directional move is weak (efficiency ~{directional_efficiency:.2f}).")

    # chop penalties / bonuses
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

    # volatility sanity: tiny overall range is bad
    if total_range < 2 * avg_range:
        clean_score -= 0.15
        reasons.append("Overall range is small relative to average bar size (likely low energy).")

    clean_score = max(0.0, min(1.0, clean_score))

    if clean_score >= 0.6:
        status = "CLEAN"
    elif clean_score >= 0.4:
        status = "MIXED"
    else:
        status = "CHOP"

    # --- decide if longs/shorts are in bias ---
    long_ok = False
    short_ok = False

    # require both: reasonably clean AND directional bias
    if status == "CLEAN" and directional_efficiency >= 0.4:
        if bias == "BULL":
            long_ok = True
        elif bias == "BEAR":
            short_ok = True

    return PreflightResult(
        status=status,
        bias=bias,
        score=clean_score,
        reasons=reasons,
        long_ok=long_ok,
        short_ok=short_ok,
        directional_efficiency=directional_efficiency,
        net_move=net_move,
        total_range=total_range,
        strong_pushes=strong_pushes,
    )
