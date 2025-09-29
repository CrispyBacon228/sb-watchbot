from __future__ import annotations
import os, time, csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from loguru import logger
from sbwatch.adapters.databento import ohlcv_range, clamp_end
from sbwatch.strategy.ict import ICTDetector
from sbwatch.util.alerts import fmt_ict_entry, fmt_tp
from sbwatch.util.tpwatch import TPWatcher
from sbwatch.util.alerts import append_alert, alerts_log_path

DATASET = os.getenv("DB_DATASET","GLBX.MDP3")
SCHEMA  = os.getenv("DB_SCHEMA","ohlcv-1m")
SYMBOL  = os.getenv("FRONT_SYMBOL")
DIV     = int(os.getenv("PRICE_DIVISOR","1000000000"))
ALERT_ICT = os.getenv("ALERT_ICT","1") not in ("0","false","no","False")
POLL_SECONDS = int(os.getenv("LIVE_POLL_SECONDS","5"))

TZ_ET = ZoneInfo("America/New_York")

def _now_utc(): 
    return datetime.now(timezone.utc)

def _rows_last(n=3):
    end = clamp_end(_now_utc())
    start = end - timedelta(minutes=n)
    return list(ohlcv_range(DATASET, SCHEMA, SYMBOL, start, end))

def _scale(v): 
    return float(v)/DIV

def _in_sb_am(ts_utc: datetime) -> bool:
    s = int(os.getenv("SB_AM_START_HH","10"))  # default 10:00 ET
    e = int(os.getenv("SB_AM_END_HH","11"))   # default 11:00 ET
    t = ts_utc.astimezone(TZ_ET)
    return s <= t.hour < e

@dataclass
class State:
    last_alert: dict

def run_live():
    from sbwatch.adapters.discord import send_discord
    if not SYMBOL:
        raise RuntimeError("FRONT_SYMBOL missing")
    send_discord(f"🟢 sb-watchbot live `{SYMBOL}` (ICT={ALERT_ICT})")

    state = State(last_alert={})
    from sbwatch.util.gate import Gate
    gate = Gate()
    tpw = TPWatcher(SYMBOL, send_discord)
    ict = ICTDetector()

    while True:
        try:
            rows = _rows_last(3)
            if not rows:
                time.sleep(POLL_SECONDS); 
                continue

            r = rows[-1]
            ts_attr = getattr(r,"ts_recv", None) or getattr(r,"ts_event", None)
            ts = datetime.fromtimestamp(float(ts_attr)/1e9, tz=timezone.utc) if ts_attr else _now_utc()

            # robust OHLC reads across schema variants
            o = _scale(getattr(r,"open",  getattr(r,"o",0.0)))
            h = _scale(getattr(r,"high",  getattr(r,"h",0.0)))
            l = _scale(getattr(r,"low",   getattr(r,"l",0.0)))
            c = _scale(getattr(r,"close", getattr(r,"c",0.0)))

            # Only operate in AM window
            if not _in_sb_am(ts):
                time.sleep(POLL_SECONDS); 
                continue

            # ICT entries
            if ALERT_ICT:
                sigs = ict.add_bar(ts, o, h, l, c)
                for sig in sigs:
                    # gate by time/price/sweep
                    sid = getattr(sig, "sweep_id", None)
                    if not gate.allow(sig.side, ts, sig.entry, sid):
                        continue
                    # alert
                    msg = fmt_ict_entry(sig.side, sig.entry, sig.stop, sig.tp1, sig.tp2)
                    append_alert(f"ICT_{sig.side.upper()}_ENTRY", SYMBOL, sig.entry, None)
                    send_discord(msg)
                    # set TP watcher legs
                    tpw.set(sig.side, sig.tp1, sig.tp2)

            # TP notifications (if any)
            hit = tpw.check(h, l)
            if hit:
                append_alert(fmt_tp(hit['side'], hit['price']), SYMBOL, hit['price'], None)
                send_discord(fmt_tp(hit['side'], hit['price']))

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            send_discord("🔴 sb-watchbot live stopped."); break
        except Exception as e:
            logger.exception("live error: {}", e)
            time.sleep(max(POLL_SECONDS,5))
