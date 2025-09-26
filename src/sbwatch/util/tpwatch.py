from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
from sbwatch.util.alerts import fmt_tp

def _yes(v:str)->bool: return str(v).lower() in ("1","true","y","yes")

TP_NOTIFY   = _yes(os.getenv("TP_NOTIFY", "true"))
TP_EXP_MIN  = int(os.getenv("TP_EXP_MIN", "30"))

@dataclass
class OpenPos:
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    ts: datetime
    state: str = "open"   # "open" -> "tp1" -> done

class TPWatcher:
    """
    Tracks open entries for a short window and notifies on TP1/TP2 or Stop.
    Live-only state (no persistence), re-created on service restart.
    """
    def __init__(self, symbol: str, send_fn):
        self.symbol = symbol
        self.send = send_fn
        self.open: list[OpenPos] = []

    def on_entry(self, ent, ts_bar: datetime):
        if not TP_NOTIFY: 
            return
        self.open.append(OpenPos(ent.side, ent.entry, ent.stop, ent.tp1, ent.tp2, ts_bar))

    def on_bar(self, ts_bar: datetime, high: float, low: float):
        if not TP_NOTIFY or not self.open:
            return
        alive: list[OpenPos] = []
        for pos in self.open:
            # expire window
            if ts_bar - pos.ts > timedelta(minutes=TP_EXP_MIN):
                continue

            if pos.side == "bull":
                hit_tp2 = high >= pos.tp2
                hit_tp1 = high >= pos.tp1
                stopout = low  <= pos.stop
            else:
                hit_tp2 = low  <= pos.tp2
                hit_tp1 = low  <= pos.tp1
                stopout = high >= pos.stop

            if stopout:
                self.send(f"❌ **Stop Out**\n**Symbol:** {self.symbol}\n**Fill:** `{pos.stop:.2f}`")
                continue
            if hit_tp2:
                # create a tiny object with ts for fmt_tp
                self.send(fmt_tp(self.symbol, type("E",(),{"ts":ts_bar}), 2, pos.tp2))
                continue
            if hit_tp1 and pos.state == "open":
                self.send(fmt_tp(self.symbol, type("E",(),{"ts":ts_bar}), 1, pos.tp1))
                pos.state = "tp1"
                alive.append(pos)
                continue

            alive.append(pos)

        self.open = alive
