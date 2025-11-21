import time
from typing import List, Dict, Optional, Tuple


def analyze_preflight_v2(
    bars: List[Dict],
    levels: Dict[str, float],
    now_ts: Optional[float] = None,
) -> Dict:
    """
    bars: list of 1m bars from MIDNIGHT -> now
           each = {"ts": <unix_seconds>, "o": float, "h": float, "l": float, "c": float}
    levels: dict that may contain:
        "asia_high", "asia_low",
        "london_high", "london_low",
        "pdh", "pdl",
        "nine_high", "nine_low"
    now_ts: override "current time" (mostly for testing)
    """
    if not bars:
        raise ValueError("analyze_preflight_v2: no bars provided")

    now_ts = now_ts or time.time()

    # 1) HTF sweeps (midnight -> now)
    tick_size = 0.25            # adjust if needed for your feed
    buffer_points = 4 * tick_size  # how far beyond level counts as CLEAN

    htf_sweeps = []

    def add_sweep(key: str, name: str, is_high: bool):
        lvl = levels.get(key)
        if lvl is None:
            return
        info = _classify_sweep_for_level(bars, lvl, is_high, name, buffer_points)
        htf_sweeps.append(info)

    add_sweep("nine_high", "9AM_HIGH", True)
    add_sweep("nine_low", "9AM_LOW", False)
    add_sweep("asia_high", "ASIA_HIGH", True)
    add_sweep("asia_low", "ASIA_LOW", False)
    add_sweep("london_high", "LONDON_HIGH", True)
    add_sweep("london_low", "LONDON_LOW", False)
    add_sweep("pdh", "PDH", True)
    add_sweep("pdl", "PDL", False)

    clean_sweeps = [s for s in htf_sweeps if s["strength"] == "CLEAN" and s["ts"] is not None]
    last_clean_sweep = max(clean_sweeps, key=lambda s: s["ts"]) if clean_sweeps else None

    freshness = _sweep_freshness(
        last_clean_sweep["ts"] if last_clean_sweep else None,
        now_ts,
    )

    disp_quality = _displacement_quality_since_sweep(
        bars,
        last_clean_sweep["ts"] if last_clean_sweep else None,
        last_clean_sweep["direction"] if last_clean_sweep else None,
    )

    # 2) Cleanliness over last 60 minutes (or fewer if not available)
    lookback = 60
    last_bars = bars[-lookback:] if len(bars) > lookback else bars

    clean_status, cleanliness, bias, direff, flip_ratio, inside_ratio = _compute_cleanliness(last_bars)

    # 3) SB readiness + long/short preferences
    sb_state, long_ok, short_ok = _sb_readiness(
        clean_status,
        last_clean_sweep,
        freshness,
        disp_quality,
        bias,
    )

    return {
        "status": clean_status,                 # "CLEAN" / "MIXED" / "CHOP"
        "cleanliness": cleanliness,             # 0.0 - 1.0
        "bias": bias,                           # "BULL" / "BEAR" / "NEUTRAL"
        "directional_efficiency": direff,
        "flip_ratio": flip_ratio,
        "inside_ratio": inside_ratio,

        "htf_sweeps": htf_sweeps,              # list of dicts
        "last_clean_sweep": last_clean_sweep,  # or None
        "sweep_freshness": freshness,          # "FRESH" / "STALE" / "DEAD"
        "disp_quality": disp_quality,          # "STRONG" / "OK" / "WEAK" / "NONE"

        "sb_state": sb_state,                  # "SB_READY_LONG" / "SB_READY_SHORT" / "SB_WAITING_FOR_SWEEP" / "SB_NO_GO"
        "long_ok": long_ok,
        "short_ok": short_ok,
    }


# ----------------- Helper functions ----------------- #

def _classify_sweep_for_level(
    bars: List[Dict],
    level: float,
    is_high: bool,
    name: str,
    buffer_points: float,
) -> Dict:
    """
    Decide if we had:
    - CLEAN sweep: extends >= buffer_points beyond level AND closes back inside soon
    - WEAK sweep: tiny poke beyond
    - NONE: never really cleared it
    Returns dict with keys: name, level, strength, ts, direction
    """
    best_strength = "NONE"      # "NONE" / "WEAK" / "CLEAN"
    best_ts = None
    direction = None

    for i, b in enumerate(bars):
        h = b["h"]
        l = b["l"]
        c = b["c"]
        ts = b["ts"]

        if is_high:
            if h <= level:
                continue
            over = h - level
            if over >= buffer_points:
                # need close back below level in this or next bar
                close_back = c < level or (
                    i + 1 < len(bars) and bars[i + 1]["c"] < level
                )
                if close_back:
                    best_strength = "CLEAN"
                    best_ts = ts
                    direction = "UP"
            else:
                if best_strength == "NONE":
                    best_strength = "WEAK"
                    best_ts = ts
                    direction = "UP"
        else:
            if l >= level:
                continue
            under = level - l
            if under >= buffer_points:
                close_back = c > level or (
                    i + 1 < len(bars) and bars[i + 1]["c"] > level
                )
                if close_back:
                    best_strength = "CLEAN"
                    best_ts = ts
                    direction = "DOWN"
            else:
                if best_strength == "NONE":
                    best_strength = "WEAK"
                    best_ts = ts
                    direction = "DOWN"

    return {
        "name": name,
        "level": level,
        "strength": best_strength,
        "ts": best_ts,
        "direction": direction,
    }


def _sweep_freshness(last_ts: Optional[float], now_ts: float) -> str:
    if last_ts is None:
        return "DEAD"
    dt_min = (now_ts - last_ts) / 60.0
    if dt_min <= 45.0:
        return "FRESH"
    if dt_min <= 120.0:
        return "STALE"
    return "DEAD"


def _compute_cleanliness(
    bars: List[Dict],
) -> Tuple[str, float, str, float, float, float]:
    """
    Returns:
      status, cleanliness, bias, directional_efficiency, flip_ratio, inside_ratio
    """
    if len(bars) < 3:
        return "CHOP", 0.0, "NEUTRAL", 0.0, 0.0, 0.0

    highs = [b["h"] for b in bars]
    lows = [b["l"] for b in bars]
    opens = [b["o"] for b in bars]
    closes = [b["c"] for b in bars]

    net_move = closes[-1] - opens[0]
    total_range = max(highs) - min(lows)
    directional_eff = abs(net_move) / total_range if total_range > 0 else 0.0

    if net_move > 0:
        bias = "BULL"
    elif net_move < 0:
        bias = "BEAR"
    else:
        bias = "NEUTRAL"

    # flip-flop ratio
    signs = []
    for o, c in zip(opens, closes):
        if c > o:
            signs.append(1)
        elif c < o:
            signs.append(-1)
        else:
            signs.append(0)

    flips = 0
    for i in range(1, len(signs)):
        if signs[i] != 0 and signs[i - 1] != 0 and signs[i] != signs[i - 1]:
            flips += 1
    flip_ratio = flips / max(1, len(signs) - 1)

    # inside-bar ratio
    inside = 0
    for i in range(1, len(bars)):
        prev = bars[i - 1]
        cur = bars[i]
        if cur["h"] <= prev["h"] and cur["l"] >= prev["l"]:
            inside += 1
    inside_ratio = inside / max(1, len(bars) - 1)

    raw = (
        directional_eff * 0.5
        + (1.0 - flip_ratio) * 0.25
        + (1.0 - inside_ratio) * 0.25
    )
    cleanliness = max(0.0, min(1.0, raw))

    if cleanliness >= 0.6:
        status = "CLEAN"
    elif cleanliness >= 0.4:
        status = "MIXED"
    else:
        status = "CHOP"

    return status, cleanliness, bias, directional_eff, flip_ratio, inside_ratio


def _displacement_quality_since_sweep(
    bars: List[Dict],
    sweep_ts: Optional[float],
    direction: Optional[str],
) -> str:
    """
    Very rough “how hard did we push AFTER the last clean sweep?”
    Returns: "STRONG", "OK", "WEAK", "NONE"
    """
    if sweep_ts is None or direction is None:
        return "NONE"

    after = [b for b in bars if b["ts"] > sweep_ts]
    if len(after) < 3:
        return "NONE"

    ranges = [b["h"] - b["l"] for b in after]
    bodies = [abs(b["c"] - b["o"]) for b in after]
    avg_range = max(0.25, sum(ranges) / len(ranges))

    strong = 0
    ok = 0
    for r, body in zip(ranges, bodies):
        if r <= 0:
            continue
        disp_ratio = body / r
        big_body = body >= 0.75 * avg_range
        if disp_ratio >= 0.6 and big_body:
            strong += 1
        elif disp_ratio >= 0.4 and body >= 0.5 * avg_range:
            ok += 1

    if strong >= 2:
        return "STRONG"
    if strong == 1 or ok >= 2:
        return "OK"
    if ok == 1:
        return "WEAK"
    return "NONE"


def _sb_readiness(
    clean_status: str,
    last_sweep: Optional[Dict],
    freshness: str,
    disp_quality: str,
    bias: str,
) -> Tuple[str, bool, bool]:
    """
    Returns:
      sb_state, long_ok, short_ok
    """
    if last_sweep is None or last_sweep.get("strength") != "CLEAN":
        return "SB_WAITING_FOR_SWEEP", False, False

    if clean_status == "CHOP" or freshness == "DEAD" or disp_quality in ("NONE", "WEAK"):
        return "SB_NO_GO", False, False

    if bias == "BULL":
        return "SB_READY_LONG", True, False
    if bias == "BEAR":
        return "SB_READY_SHORT", False, True

    return "SB_WAITING_FOR_SWEEP", False, False
