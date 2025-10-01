from collections import deque
from datetime import time as dtime, timedelta
import pytz

NY = pytz.timezone("America/New_York")

# ---- Silver Bullet session: strictly 10:00–11:00 NY ----
SESSION_START = dtime(10, 0)
SESSION_END   = dtime(11, 0)

# ---- Quality gates (moderate) ----
MIN_DISP_PTS   = 1.5      # middle candle total range
MIN_BODY_FRAC  = 0.45     # middle candle body >= 45% of range
MIN_ZONE_PTS   = 0.75     # ignore micro FVGs
FRESH_MAX_BARS = 6        # touch must happen within 6 bars of creation
REQUIRE_OUTSIDE_IN = True # touch must return from outside
CONFIRM_PTS    = 0.25     # touch bar closes in direction by >= 0.25
COOLDOWN_MIN   = 3        # per direction

# ---- NQ tick => for stop padding ----
TICK = 0.25

bars = deque(maxlen=4)
active_fvgs = []  # dict: direction, low, high, created_ts, created_bar_idx, touched
bar_index = 0
last_alert_ts_by_dir = {+1: None, -1: None}

def _ensure_utc(ts):
    if getattr(ts, "tzinfo", None) is None:
        return pytz.UTC.localize(ts)
    try:
        return ts.tz_convert("UTC")
    except Exception:
        return ts

def _in_session(ts_utc):
    t = _ensure_utc(ts_utc).tz_convert(NY).time()
    return SESSION_START <= t <= SESSION_END

def _range(row): return float(row["high"] - row["low"])
def _body(row):  return float(row["close"] - row["open"])

def _is_displacement(row):
    rng = _range(row)
    if rng < MIN_DISP_PTS:
        return 0
    body = _body(row)
    if body > 0 and body >= MIN_BODY_FRAC * rng:
        return +1
    if body < 0 and -body >= MIN_BODY_FRAC * rng:
        return -1
    return 0

def _maybe_create_fvg(a, b, c, middle_dir, created_bar_idx):
    # 3-bar FVG (a,b,c) with b = displacement candle
    if middle_dir > 0 and float(a["high"]) < float(c["low"]):
        low, high = float(a["high"]), float(c["low"])
        if high - low >= MIN_ZONE_PTS:
            active_fvgs.append({
                "direction": +1,
                "low": low, "high": high,
                "created_ts": c["timestamp"],
                "created_bar_idx": created_bar_idx,
                "touched": False
            })
    elif middle_dir < 0 and float(a["low"]) > float(c["high"]):
        low, high = float(c["high"]), float(a["low"])
        if high - low >= MIN_ZONE_PTS:
            active_fvgs.append({
                "direction": -1,
                "low": low, "high": high,
                "created_ts": c["timestamp"],
                "created_bar_idx": created_bar_idx,
                "touched": False
            })

def _cooldown_ok(ts, direction):
    last = last_alert_ts_by_dir.get(direction)
    if not last:
        return True
    return (_ensure_utc(ts) - last) >= timedelta(minutes=COOLDOWN_MIN)

def _fmt_sb_alert(ts_utc, side, entry, zlow, zhigh, stop):
    ts_ny = _ensure_utc(ts_utc).tz_convert(NY).strftime("%Y-%m-%d %H:%M:%S %Z")
    risk = abs(entry - stop)
    tp1  = entry + (risk if side == "LONG" else -risk)
    tp2  = entry + (2*risk if side == "LONG" else -2*risk)
    # ICT SB-style content: side, time, entry, FVG, SL, R, TP1/TP2
    return (
        f"SB ENTRY {side} | {ts_ny} | "
        f"Entry {entry:.2f} | FVG[{zlow:.2f},{zhigh:.2f}] | "
        f"SL {stop:.2f} | 1R {tp1:.2f} | 2R {tp2:.2f}"
    )

def on_bar(row, verbose=False):
    global bar_index
    bar_index += 1
    alerts = []

    ts = _ensure_utc(row["timestamp"])
    if not _in_session(ts):
        return None

    bars.append(row)

    # 1) Create FVGs when we have a,b,c (c is the newest bar)
    if len(bars) >= 3:
        a, b, c = bars[-3], bars[-2], bars[-1]
        middle_dir = _is_displacement(b)
        if middle_dir != 0:
            _maybe_create_fvg(a, b, c, middle_dir, bar_index)

    # 2) First return / touch with filters, then format “SB” alert
    lo, hi, close, opn = float(row["low"]), float(row["high"]), float(row["close"]), float(row["open"])
    prev = bars[-2] if len(bars) >= 2 else None
    prev_lo = float(prev["low"]) if prev is not None else None
    prev_hi = float(prev["high"]) if prev is not None else None

    for fvg in active_fvgs:
        if fvg["touched"]:
            continue
        if (bar_index - fvg["created_bar_idx"]) > FRESH_MAX_BARS:
            continue
        # overlap?
        if hi < fvg["low"] or lo > fvg["high"]:
            continue
        # outside-in?
        if REQUIRE_OUTSIDE_IN and prev is not None:
            was_outside = (prev_hi < fvg["low"]) or (prev_lo > fvg["high"])
            if not was_outside:
                continue
        # confirm close direction on touch bar
        body = close - opn
        if fvg["direction"] == +1:
            if body <  CONFIRM_PTS:  # need bullish close by >= CONFIRM_PTS
                continue
            side  = "LONG"
            entry = min(max(close, fvg["low"]), fvg["high"])
            stop  = fvg["low"] - TICK
        else:
            if -body < CONFIRM_PTS:  # need bearish close
                continue
            side  = "SHORT"
            entry = min(max(close, fvg["low"]), fvg["high"])
            stop  = fvg["high"] + TICK

        # cooldown per direction
        if not _cooldown_ok(ts, fvg["direction"]):
            continue

        # fire once
        fvg["touched"] = True
        last_alert_ts_by_dir[fvg["direction"]] = ts
        alerts.append(_fmt_sb_alert(ts, side, entry, fvg["low"], fvg["high"], stop))

    return alerts if alerts else None
