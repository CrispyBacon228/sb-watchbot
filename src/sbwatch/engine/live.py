from __future__ import annotations
import os, time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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

@dataclass
class State:
    prev_price: float | None = None
    last_alert: dict | None = None

def _now_utc():
    return datetime.now(timezone.utc)

def _rows_last_minutes(minutes_back: int = 20):
    """Fetch recent minute bars; returns a list of records."""
    end = clamp_end(_now_utc())
    start = end - timedelta(minutes=minutes_back)
    return list(ohlcv_range(DATASET, SCHEMA, SYMBOL, start, end))

def _fld(rec, a, b=None):
    v = getattr(rec, a, None)
    if v is None and b is not None:
        v = getattr(rec, b, None)
    return v

def _hlc_scaled(rec):
    """Return high, low, close scaled by DIV; support OHLCVMsg or dict-like."""
    # attributes preferred
    h = _fld(rec, "high", "h"); l = _fld(rec, "low", "l"); c = _fld(rec, "close", "c")
    if h is None and isinstance(rec, dict):
        h = rec.get("high", rec.get("h"))
        l = rec.get("low",  rec.get("l"))
        c = rec.get("close", rec.get("c"))
    if h is None or l is None:
        raise TypeError(f"Unexpected row type: {type(rec)} has no high/low")
    if c is None:
        # fallback to mid if no close present
        c = (float(h) + float(l)) / 2.0
    return float(h)/DIV, float(l)/DIV, float(c)/DIV

def _should_alert(state: State, key: str) -> bool:
    now = time.time()
    state.last_alert = state.last_alert or {}
    last = state.last_alert.get(key, 0)
    if now - last < COOLDOWN_SEC:
        return False
    state.last_alert[key] = now
    return True

def run_live() -> None:
    from sbwatch.adapters.discord import send_discord
    if not SYMBOL:
        raise RuntimeError("FRONT_SYMBOL missing in env (.env)")

    lv = load_levels(LEVELS_PATH)
    logger.info("LIVE start: symbol={}, dataset={}, schema={}, levels={}",
                SYMBOL, DATASET, SCHEMA, LEVELS_PATH)
    send_discord(
        f"🟢 sb-watchbot live for `{SYMBOL}` | "
        f"PDH {lv.pdh:.2f} / PDL {lv.pdl:.2f} | "
        f"Asia {lv.asia_low:.2f}-{lv.asia_high:.2f} | "
        f"London {lv.london_low:.2f}-{lv.london_high:.2f} | "
        f"Mode: {'WICK_ONLY' if WICK_ONLY else 'CROSS+WICK'} • Tol={TOL_TICKS} ticks"
    )

    state = State(prev_price=None, last_alert={})

    while True:
        try:
            rows = _rows_last_minutes(20)
            if not rows:
                logger.warning("No recent data; retrying in {}s", POLL_SECONDS)
                time.sleep(POLL_SECONDS); continue

            # use the last completed bar (last item is fine for 1m historical pulls)
            h, l, c = _hlc_scaled(rows[-1])
            last_price = c

            # ----- WICK REJECT LOGIC -----
            pdh_reject = (h >= lv.pdh + TOL) and (c < lv.pdh)
            pdl_reject = (l <= lv.pdl - TOL) and (c > lv.pdl)

            if pdh_reject and _should_alert(state, "PDH_REJECT"):
                send_discord(f"🟣 {SYMBOL} PDH reject: wick above by ≥{TOL_TICKS}t, close back below · "
                             f"close {c:.2f} · PDH {lv.pdh:.2f}")
            if pdl_reject and _should_alert(state, "PDL_REJECT"):
                send_discord(f"🟠 {SYMBOL} PDL reject: wick below by ≥{TOL_TICKS}t, close back above · "
                             f"close {c:.2f} · PDL {lv.pdl:.2f}")

            # ----- SIMPLE CROSSES (optional) -----
            if not WICK_ONLY and state.prev_price is not None:
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
            send_discord("🔴 sb-watchbot live stopped.")
            break
        except Exception as e:
            logger.exception("Live loop error: {}", e)
            time.sleep(max(POLL_SECONDS, 5))
