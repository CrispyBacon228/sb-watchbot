#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import time
import datetime as dt
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from zoneinfo import ZoneInfo

# Try to import notify; if that fails, fall back to print-only mode
try:
    from sbwatch import notify  # type: ignore
except Exception:
    notify = None  # type: ignore

ET = ZoneInfo("America/New_York")

DATA_PATH = Path("data/live_minute.csv")
LEVELS_PATH = Path("data/levels.json")


def load_all_bars() -> List[Dict]:
    """
    Load all 1m bars from live_minute.csv.
    Each row becomes:
        {"ts": unix_seconds, "ts_ms": int, "dt": datetime_ET,
         "o":..., "h":..., "l":..., "c":...}
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} not found")

    bars: List[Dict] = []
    with DATA_PATH.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts_ms = int(float(row.get("ts_ms") or row.get("timestamp") or row.get("ts")))
                o = float(row.get("open") or row.get("o"))
                h = float(row.get("high") or row.get("h"))
                l = float(row.get("low") or row.get("l"))
                c = float(row.get("close") or row.get("c"))
            except Exception:
                continue
            ts = ts_ms / 1000.0
            dt_et = dt.datetime.fromtimestamp(ts, tz=ET)
            bars.append(
                {
                    "ts_ms": ts_ms,
                    "ts": ts,
                    "dt": dt_et,
                    "o": o,
                    "h": h,
                    "l": l,
                    "c": c,
                }
            )
    return bars


def load_levels() -> Dict[str, Optional[float]]:
    """
    Load levels.json created by sb_bot levels_cmd().
    Structure:
        {"date": "YYYY-MM-DD",
         "levels": {
             "asia_high":..., "asia_low":...,
             "london_high":..., "london_low":...,
             "pdh":..., "pdl":...
         }}
    """
    if not LEVELS_PATH.exists():
        return {}
    try:
        raw = json.loads(LEVELS_PATH.read_text(encoding="utf-8"))
        return raw.get("levels", {}) or {}
    except Exception:
        return {}


def send(msg: str) -> None:
    """Print to stdout and send to Discord if notify is available."""
    print(msg)
    if notify is not None:
        try:
            notify.post_discord(msg)  # type: ignore
        except Exception as e:
            print(f"[preflight notify error: {e}]")


def _compute_9am_range(bars: List[Dict]) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute high/low of the 9:00–10:00 ET hourly candle using 1m bars.
    """
    if not bars:
        return None, None

    any_dt = bars[-1]["dt"]
    d = any_dt.date()
    start = dt.datetime(d.year, d.month, d.day, 9, 0, tzinfo=ET)
    end = dt.datetime(d.year, d.month, d.day, 10, 0, tzinfo=ET)

    hi = None
    lo = None
    for b in bars:
        t = b["dt"]
        if not (start <= t < end):
            continue
        h = b["h"]; l = b["l"]
        hi = h if hi is None or h > hi else hi
        lo = l if lo is None or l < lo else lo

    return hi, lo


def _classify_sweep_for_level(
    bars: List[Dict],
    level: float,
    is_high: bool,
    name: str,
    buffer_points: float,
) -> Dict:
    """
    ICT sweep classifier:
      CLEAN sweep: extends >= buffer_points beyond level AND closes back inside soon
      WEAK sweep: tiny poke beyond
      NONE: never really cleared it
    Returns dict: {name, level, strength, ts, direction}
      direction: "UP"  (raided a high)
                 "DOWN"(raided a low)
    """
    best_strength = "NONE"
    best_ts: Optional[float] = None
    direction: Optional[str] = None

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
    """
    How recent is the last CLEAN sweep?
      FRESH: <= 45 min
      STALE: 45–120 min
      DEAD:  > 120 min or none
    """
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
) -> Tuple[str, float, float, float, float]:
    """
    CHOP / MIXED / CLEAN + score and diagnostics.
    Returns:
      status, cleanliness, directional_efficiency, flip_ratio, inside_ratio
    """
    if len(bars) < 3:
        return "CHOP", 0.0, 0.0, 0.0, 0.0

    highs = [b["h"] for b in bars]
    lows = [b["l"] for b in bars]
    opens = [b["o"] for b in bars]
    closes = [b["c"] for b in bars]

    net_move = closes[-1] - opens[0]
    total_range = max(highs) - min(lows)
    directional_eff = abs(net_move) / total_range if total_range > 0 else 0.0

    # flip-flop ratio (how often candles change color)
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

    return status, cleanliness, directional_eff, flip_ratio, inside_ratio


def _displacement_quality_since_sweep(
    bars: List[Dict],
    sweep_ts: Optional[float],
    sweep_direction: Optional[str],
) -> str:
    """
    ICT-style: did we get a REAL displacement AWAY from the sweep?
    - If sweep was UP (we raided a high), we want strong move DOWN.
    - If sweep was DOWN (we raided a low), we want strong move UP.
    Returns: "STRONG", "OK", "WEAK", "NONE"
    """
    if sweep_ts is None or sweep_direction is None:
        return "NONE"

    after = [b for b in bars if b["ts"] > sweep_ts]
    if len(after) < 3:
        return "NONE"

    start_close = after[0]["c"]
    end_close = after[-1]["c"]
    net = end_close - start_close

    if sweep_direction == "UP":
        signed_push = -net  # want down
    else:
        signed_push = net   # want up

    total_range = max(b["h"] for b in after) - min(b["l"] for b in after)
    if total_range <= 0:
        return "NONE"

    push_ratio = signed_push / total_range

    if push_ratio >= 0.6:
        return "STRONG"
    if push_ratio >= 0.3:
        return "OK"
    if push_ratio > 0:
        return "WEAK"
    return "NONE"


def _sb_bias_from_sweep(last_sweep: Optional[Dict]) -> str:
    """
    ICT SB directional trading bias:
      - Sweep HIGH (direction=UP)  → look for SHORTS
      - Sweep LOW  (direction=DOWN)→ look for LONGS
    """
    if not last_sweep or not last_sweep.get("direction"):
        return "FLAT"

    if last_sweep["direction"] == "UP":
        return "SHORT"
    if last_sweep["direction"] == "DOWN":
        return "LONG"
    return "FLAT"


def _sb_trading_day_state(
    clean_status: str,
    cleanliness: float,
    freshness: str,
    disp_quality: str,
    last_sweep: Optional[Dict],
) -> str:
    """
    High-level tag for the day:
      - "ICT_SB_DAY"   : fits SB conditions well
      - "SB_MAYBE"     : marginal but possible
      - "SB_AVOID"     : not an SB day (chop, no sweep, stale, no displacement)
    """
    if last_sweep is None or last_sweep.get("strength") != "CLEAN":
        return "SB_AVOID"

    if freshness == "DEAD" or disp_quality in ("NONE", "WEAK"):
        return "SB_AVOID"

    if clean_status == "CLEAN" and disp_quality == "STRONG" and cleanliness >= 0.6:
        return "ICT_SB_DAY"

    if clean_status in ("CLEAN", "MIXED") and disp_quality in ("OK", "STRONG"):
        return "SB_MAYBE"

    return "SB_AVOID"


def analyze_preflight_ict_sb(bars: List[Dict]) -> Dict:
    """
    Full ICT-SB style preflight:
      - reads Asia/London/PDH/PDL from levels.json
      - computes 9AM range
      - finds CLEAN sweeps of those levels
      - measures displacement AWAY from last CLEAN sweep
      - evaluates tape cleanliness (last 60m)
      - labels:
          * SB bias (LONG/SHORT)
          * SB trading-day state (ICT_SB_DAY / SB_MAYBE / SB_AVOID)
    """
    if not bars:
        raise ValueError("no bars loaded for preflight")

    now_ts = bars[-1]["ts"]

    levels_raw = load_levels()
    nine_high, nine_low = _compute_9am_range(bars)

    levels: Dict[str, Optional[float]] = {
        "nine_high": nine_high,
        "nine_low": nine_low,
        "asia_high": levels_raw.get("asia_high"),
        "asia_low": levels_raw.get("asia_low"),
        "london_high": levels_raw.get("london_high"),
        "london_low": levels_raw.get("london_low"),
        "pdh": levels_raw.get("pdh"),
        "pdl": levels_raw.get("pdl"),
    }

    tick_size = 0.25
    buffer_points = 4 * tick_size

    htf_sweeps: List[Dict] = []

    def add_sweep(key: str, name: str, is_high: bool) -> None:
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

    last_bars = bars[-60:] if len(bars) > 60 else bars
    clean_status, cleanliness, direff, flip_ratio, inside_ratio = _compute_cleanliness(last_bars)

    sb_bias = _sb_bias_from_sweep(last_clean_sweep)

    trading_day_state = _sb_trading_day_state(
        clean_status, cleanliness, freshness, disp_quality, last_clean_sweep
    )

    return {
        "trading_day_state": trading_day_state,
        "sb_bias": sb_bias,
        "status": clean_status,
        "cleanliness": cleanliness,
        "directional_efficiency": direff,
        "flip_ratio": flip_ratio,
        "inside_ratio": inside_ratio,
        "htf_sweeps": htf_sweeps,
        "last_clean_sweep": last_clean_sweep,
        "sweep_freshness": freshness,
        "disp_quality": disp_quality,
    }


def format_preflight_msg(pf: Dict) -> str:
    now_ts = time.time()
    ts_str = time.strftime("%H:%M ET", time.localtime(now_ts))

    state = pf["trading_day_state"]
    bias = pf["sb_bias"]

    if state == "ICT_SB_DAY":
        state_emoji = "✅"
    elif state == "SB_MAYBE":
        state_emoji = "⚠️"
    else:
        state_emoji = "❌"

    header = f"{state_emoji} SB-PREFLIGHT ({ts_str}) ➜ {state}"

    lines: List[str] = [header, ""]

    if bias == "LONG":
        bias_text = "Last clean sweep was a **LOW** → look for **LONGS** only."
    elif bias == "SHORT":
        bias_text = "Last clean sweep was a **HIGH** → look for **SHORTS** only."
    else:
        bias_text = "No clean sweep of key HTF levels yet → **no clear SB side**."

    lines.append(f"**SB Bias:** {bias_text}")
    lines.append(
        f"• Tape: **{pf['status']}** (cleanliness ~{pf['cleanliness']:.2f}) | "
        f"disp: **{pf['disp_quality']}** | sweep freshness: **{pf['sweep_freshness']}**"
    )
    lines.append("")

    last = pf["last_clean_sweep"]
    if last and last.get("ts") is not None:
        t = time.strftime("%H:%M", time.localtime(last["ts"]))
        lines.append(
            f"Last CLEAN sweep: {last['name']} at {t} (lvl {last['level']:.2f}, dir={last['direction']})"
        )
    else:
        lines.append("Last CLEAN sweep: None (no proper raid on 9AM / Asia / London / PDH/PDL).")

    return "\n".join(lines)


def main() -> None:
    try:
        all_bars = load_all_bars()
    except Exception as e:
        send(f"🧪 SB-PREFLIGHT ➜ ERROR loading minute data: {e}")
        return

    if not all_bars:
        send("🧪 SB-PREFLIGHT ➜ No minute data available.")
        return

    pf = analyze_preflight_ict_sb(all_bars)
    msg = format_preflight_msg(pf)
    send(msg)


if __name__ == "__main__":
    main()
