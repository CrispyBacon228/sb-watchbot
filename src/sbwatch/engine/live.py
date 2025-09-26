from __future__ import annotations
import os, time, os.path
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time as dtime
from zoneinfo import ZoneInfo
from loguru import logger
from sbwatch.core.levels import load_levels
from sbwatch.adapters.databento import ohlcv_range, clamp_end

DATASET = os.getenv("DB_DATASET", "GLBX.MDP3")
SCHEMA  = os.getenv("DB_SCHEMA",  "ohlcv-1m")
SYMBOL  = os.getenv("FRONT_SYMBOL")
LEVELS_PATH = os.getenv("LEVELS_PATH", "./data/levels.json")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))
COOLDOWN_SEC = int(os.getenv("COOLDOWN_SEC", "300"))
DIV = int(os.getenv("PRICE_DIVISOR", "1000000000"))
TICK_SIZE = float(os.getenv("TICK_SIZE", "0.25"))
TOL_TICKS = int(os.getenv("TOL_TICKS", "4"))
TOL = TICK_SIZE * TOL_TICKS
WICK_ONLY = os.getenv("WICK_ONLY", "true").lower() in ("1","true","yes","y")

ENABLE_KILLZONE = os.getenv("ENABLE_KILLZONE", "true").lower() in ("1","true","yes","y")
KZ1_START = os.getenv("KZ1_START", "09:30")
KZ1_END   = os.getenv("KZ1_END",   "11:00")
KZ2_START = os.getenv("KZ2_START", "13:30")
KZ2_END   = os.getenv("KZ2_END",   "15:30")
TZ_ET = ZoneInfo("America/New_York")

LEVELS_RELOAD_SEC = int(os.getenv("LEVELS_RELOAD_SEC", "60"))
HEARTBEAT_MIN = int(os.getenv("HEARTBEAT_MIN", "0"))

@dataclass
class State:
    prev_price: float | None = None
    last_alert: dict | None = None

def _parse_hhmm(s: str) -> dtime:
    hh, mm = s.split(":"); return dtime(int(hh), int(mm), tzinfo=TZ_ET)

def _in_killzone_now() -> bool:
    if not ENABLE_KILLZONE:
        return True
    now = datetime.now(TZ_ET).time().replace(tzinfo=TZ_ET)
    kz = [(_parse_hhmm(KZ1_START), _parse_hhmm(KZ1_END)),
          (_parse_hhmm(KZ2_START), _parse_hhmm(KZ2_END))]
    return any(a <= now <= b for a, b in kz)

def _now_utc(): return datetime.now(timezone.utc)

def _rows_last_minutes(minutes_back: int = 20):
    end = clamp_end(_now_utc()); start = end - timedelta(minutes=minutes_back)
    return list(ohlcv_range(DATASET, SCHEMA, SYMBOL, start, end))

def _fld(rec, a, b=None):
    v = getattr(rec, a, None)
    if v is None and b is not None: v = getattr(rec, b, None)
    return v

def _hlc_scaled(rec):
    h = _fld(rec, "high", "h"); l = _fld(rec, "low", "l"); c = _fld(rec, "close", "c")
    if h is None and isinstance(rec, dict):
        h = rec.get("high", rec.get("h")); l = rec.get("low", rec.get("l")); c = rec.get("close", rec.get("c"))
    if h is None or l is None: raise TypeError(f"Unexpected row type: {type(rec)} has no high/low")
    if c is None: c = (float(h) + float(l)) / 2.0
    return float(h)/DIV, float(l)/DIV, float(c)/DIV

def _should_alert(state: State, key: str) -> bool:
    if not _in_killzone_now(): return False
    now = time.time(); state.last_alert = state.last_alert or {}
    last = state.last_alert.get(key, 0)
    if now - last < COOLDOWN_SEC: return False
    state.last_alert[key] = now; return True

def _et_date_iso() -> str:
    return datetime.now(TZ_ET).date().isoformat()

def run_live() -> None:
    from sbwatch.adapters.discord import send_discord
    if not SYMBOL: raise RuntimeError("FRONT_SYMBOL missing in env (.env)")

    lv = load_levels(LEVELS_PATH)
    logger.info("LIVE start: symbol={}, dataset={}, schema={}, levels={}",
                SYMBOL, DATASET, SCHEMA, LEVELS_PATH)
    send_discord(
        f"🟢 sb-watchbot live for `{SYMBOL}` | "
        f"PDH {lv.pdh:.2f} / PDL {lv.pdl:.2f} | "
        f"Asia {lv.asia_low:.2f}-{lv.asia_high:.2f} | "
        f"London {lv.london_low:.2f}-{lv.london_high:.2f} | "
        f"Mode: {'WICK_ONLY' if WICK_ONLY else 'CROSS+WICK'} • Tol={TOL_TICKS}t"
    )

    # track file mtime + ET date to auto-reload levels
    try:
        last_mtime = os.path.getmtime(LEVELS_PATH)
    except FileNotFoundError:
        last_mtime = 0.0
    last_reload_check = time.time()
    current_et_date = lv.date_et
    next_heartbeat = time.time() + HEARTBEAT_MIN*60 if HEARTBEAT_MIN > 0 else float("inf")

    state = State(prev_price=None, last_alert={})

    while True:
        try:
            # periodic reload check
            now = time.time()
            if now - last_reload_check >= LEVELS_RELOAD_SEC:
                last_reload_check = now
                et_now = _et_date_iso()
                try:
                    mtime = os.path.getmtime(LEVELS_PATH)
                except FileNotFoundError:
                    mtime = last_mtime
                if et_now != current_et_date or mtime != last_mtime:
                    lv = load_levels(LEVELS_PATH)
                    current_et_date = lv.date_et
                    last_mtime = mtime
                    send_discord(f"🔄 reloaded levels for {lv.date_et} · "
                                 f"PDH {lv.pdh:.2f} / PDL {lv.pdl:.2f} · "
                                 f"Asia {lv.asia_low:.2f}-{lv.asia_high:.2f} · "
                                 f"London {lv.london_low:.2f}-{lv.london_high:.2f}")

            # heartbeat
            if now >= next_heartbeat:
                send_discord("💚 heartbeat: sb-watchbot running")
                next_heartbeat = now + HEARTBEAT_MIN*60

            rows = _rows_last_minutes(20)
            if not rows:
                time.sleep(POLL_SECONDS); continue

            h, l, c = _hlc_scaled(rows[-1])
            last_price = c

            # --- wick rejects for PDH/PDL + Asia/London ---
            signals = {
                "PDH_REJECT":     (h >= lv.pdh         + TOL) and (c < lv.pdh),
                "PDL_REJECT":     (l <= lv.pdl         - TOL) and (c > lv.pdl),
                "ASIA_H_REJECT":  (h >= lv.asia_high   + TOL) and (c < lv.asia_high),
                "ASIA_L_REJECT":  (l <= lv.asia_low    - TOL) and (c > lv.asia_low),
                "LON_H_REJECT":   (h >= lv.london_high + TOL) and (c < lv.london_high),
                "LON_L_REJECT":   (l <= lv.london_low  - TOL) and (c > lv.london_low),
            }
            for name, hit in signals.items():
                if hit and _should_alert(state, name):
                    label = name.replace("_REJECT","")
                    arrow = "🟣" if "H" in name else "🟠"
                    level_val = {
                        "PDH": lv.pdh, "PDL": lv.pdl,
                        "ASIA_H": lv.asia_high, "ASIA_L": lv.asia_low,
                        "LON_H": lv.london_high, "LON_L": lv.london_low
                    }[label]
                    send_discord(f"{arrow} {SYMBOL} {label} reject · wick ≥{TOL_TICKS}t, close back in · "
                                 f"close {c:.2f} · level {level_val:.2f}")

            # optional simple crosses
            if not WICK_ONLY and state.prev_price is not None and _in_killzone_now():
                def _up(prev, cur, lvl):   return prev < lvl <= cur
                def _down(prev, cur, lvl): return prev > lvl >= cur
                crosses = {
                    "PDH_UP":   _up(state.prev_price, last_price, lv.pdh),
                    "PDH_DOWN": _down(state.prev_price, last_price, lv.pdh),
                    "PDL_UP":   _up(state.prev_price, last_price, lv.pdl),
                    "PDL_DOWN": _down(state.prev_price, last_price, lv.pdl),
                }
                for name, hit in crosses.items():
                    if hit and _should_alert(state, name):
                        arrow = "▲" if name.endswith("UP") else "▼"
                        lvlname = name.split("_")[0]
                        send_discord(f"⚡ {SYMBOL} {arrow} cross {lvlname} at {last_price:.2f} "
                                     f"(PDH {lv.pdh:.2f} / PDL {lv.pdl:.2f})")

            state.prev_price = last_price
            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Stopping live watcher (CTRL-C)")
            from sbwatch.adapters.discord import send_discord
            send_discord("🔴 sb-watchbot live stopped.")
            break
        except Exception as e:
            logger.exception("Live loop error: {}", e)
            time.sleep(max(POLL_SECONDS, 5))
