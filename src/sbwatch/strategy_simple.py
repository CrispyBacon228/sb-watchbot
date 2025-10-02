from collections import deque
from datetime import time
import zoneinfo

# Globals so state survives across on_bar() calls
_prev = deque(maxlen=2)           # last 2 bars
_open_long = []                   # [{"lo":..,"hi":..,"touched":False}]
_open_short = []
NY = zoneinfo.ZoneInfo("America/New_York")

def _in_killzone(ts_utc):
    ny = ts_utc.astimezone(NY)
    return time(10,0) <= ny.time() < time(11,0)

def _fmt_alert(side, ts_utc, entry, zlo, zhi, sl, r1, r2):
    ny_str = ts_utc.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S %Z")
    return (f"[ALERT] SB ENTRY {side} | {ny_str} | "
            f"Entry {entry:.2f} | FVG[{zlo:.2f},{zhi:.2f}] | "
            f"SL {sl:.2f} | 1R {r1:.2f} | 2R {r2:.2f}")

def reset():
    _prev.clear()
    _open_long.clear()
    _open_short.clear()

def on_bar(row):
    """
    row: dict-like with keys: timestamp (tz-aware UTC), open, high, low, close
    Returns list[str] of alert lines (possibly empty)
    """
    alerts = []

    ts = row["timestamp"]   # tz-aware UTC expected
    high = float(row["high"])
    low  = float(row["low"])

    # Only process + alert inside killzone (10:00–11:00 ET)
    if not _in_killzone(ts):
        _prev.append(row)
        return alerts

    # 3-bar FVG creation requires i-2
    if len(_prev) == 2:
        p2 = _prev[0]  # two bars back
        p2_high = float(p2["high"])
        p2_low  = float(p2["low"])

        # Bullish FVG: low[i] > high[i-2] => zone [high[i-2], low[i]]
        if low > p2_high:
            _open_long.append({"lo": p2_high, "hi": low, "touched": False})

        # Bearish FVG: high[i] < low[i-2] => zone [high[i], low[i-2]]
        if high < p2_low:
            _open_short.append({"lo": high, "hi": p2_low, "touched": False})

    # Touch checks
    # LONG zones touched if bar range intersects zone
    for z in _open_long:
        if not z["touched"] and (row["low"] <= z["hi"] and row["high"] >= z["lo"]):
            z["touched"] = True
            entry = z["hi"]
            sl    = z["lo"] - 0.25
            r     = entry - sl
            r1    = entry + r
            r2    = entry + 2*r
            alerts.append(_fmt_alert("LONG", ts, entry, z["lo"], z["hi"], sl, r1, r2))

    # SHORT zones touched if bar range intersects zone
    for z in _open_short:
        if not z["touched"] and (row["high"] >= z["lo"] and row["low"] <= z["hi"]):
            z["touched"] = True
            entry = z["lo"]
            sl    = z["hi"] + 0.25
            r     = sl - entry
            r1    = entry - r
            r2    = entry - 2*r
            alerts.append(_fmt_alert("SHORT", ts, entry, z["lo"], z["hi"], sl, r1, r2))

    _prev.append(row)
    return alerts
