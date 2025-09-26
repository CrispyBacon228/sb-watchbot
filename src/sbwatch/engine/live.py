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
POLL_SECONDS   = int(os.getenv("POLL_SECONDS","5"))
COOLDOWN_SEC   = int(os.getenv("COOLDOWN_SEC","300"))
ALERT_ICT      = os.getenv("ALERT_ICT","true").lower() in ("1","true","yes","y")

ENABLE_KILLZONE= os.getenv("ENABLE_KILLZONE","true").lower() in ("1","true","yes","y")
KZ1_START=os.getenv("KZ1_START","09:30"); KZ1_END=os.getenv("KZ1_END","11:00")
KZ2_START=os.getenv("KZ2_START","13:30"); KZ2_END=os.getenv("KZ2_END","15:30")
TZ_ET = ZoneInfo("America/New_York")

def _in_killzone() -> bool:
    if not ENABLE_KILLZONE: return True
    t = datetime.now(TZ_ET).time()
    def inside(a,b):
        ah,am = map(int,a.split(":")); bh,bm = map(int,b.split(":"))
        return (ah,am) <= (t.hour,t.minute) <= (bh,bm)
    return inside(KZ1_START,KZ1_END) or inside(KZ2_START,KZ2_END)

@dataclass
class State:
    last_alert: dict

def _now_utc(): return datetime.now(timezone.utc)
def _rows_last(n=3):
    end = clamp_end(_now_utc()); start = end - timedelta(minutes=n)
    return list(ohlcv_range(DATASET, SCHEMA, SYMBOL, start, end))
def _scale(v): return float(v)/DIV

def run_live():
    from sbwatch.adapters.discord import send_discord
    if not SYMBOL: raise RuntimeError("FRONT_SYMBOL missing")
    send_discord(f"🟢 sb-watchbot live `{SYMBOL}` (ICT={ALERT_ICT})")
    state = State(last_alert={})
    from sbwatch.util.gate import Gate
    gate = Gate()
    tpw = TPWatcher(symbol, send_discord)
    ict = ICTDetector()

    while True:
        try:
            rows = _rows_last(3)
            if not rows:
                time.sleep(POLL_SECONDS); continue
            r = rows[-1]
            ts_attr = getattr(r,"ts_recv", None) or getattr(r,"ts_event", None)
            ts = datetime.fromtimestamp(float(ts_attr)/1e9, tz=timezone.utc) if ts_attr else _now_utc()
            o = _scale(getattr(r,"open",getattr(r,"o",0.0)))
            h = _scale(getattr(r,"high",getattr(r,"h",0.0)))
            l = _scale(getattr(r,"low", getattrib:=getattr(r,"l",0.0)))
            l = _scale(getattr(r,"low",getattr(r,"l",0.0)))
            c = _scale(getattr(r,"close",getattr(r,"c",0.0)))

            if ALERT_ICT and _in_killzone():
                signals = ict.add_bar(ts,o,h,l,c)
                for sig in signals:
                    # gate overlapping/near-duplicate entries
                    if not gate.allow(sig.side, sig.entry, getattr(sig, 'sweep_id', None)):
                        continue

                    et = datetime.now(TZ_ET).strftime("%H:%M:%S")
                    block = [
                        "✅ Silver Bullet Entry Confirmed",
                        f"Symbol: {SYMBOL}",
                        f"Time: {et} ET",
                        f"Setup: {sig.context}",
                        f"Entry: {sig.entry:.2f}",
                        f"Stop: {sig.stop:.2f}",
                        f"TP1: {sig.tp1:.2f}",
                        f"TP2: {sig.tp2:.2f}",
                        f"Projected fill window: {os.getenv('ENTRY_WINDOW_MIN','15')}–{int(os.getenv('ENTRY_WINDOW_MIN','15'))+5}m",
                    ]
                    send_discord("\n".join(block))
                    append_alert(f"ICT_{sig.side.upper()}_ENTRY", SYMBOL, sig.entry, sig.stop)

            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            send_discord("🔴 sb-watchbot live stopped."); break
        except Exception as e:
            logger.exception("live error: {}", e)
            time.sleep(max(POLL_SECONDS,5))
