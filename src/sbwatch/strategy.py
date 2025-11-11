from __future__ import annotations
import os, json, datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

SB_TP_RR = float(os.environ.get("SB_TP_RR", "2.0"))
SB_SILVER_BULLET_BUFFER = 5.0

def _fv(v: str, d: float):
    try:
        return float(os.environ.get(v, d))
    except:
        return d

def _iv(v: str, d: int):
    try:
        return int(os.environ.get(v, d))
    except:
        return d

# runtime env config
FVG_MODE          = os.environ.get("FVG_MODE", "3C").upper()
SB_FVG_MIN        = _fv("SB_FVG_MIN", 15.0)
SB_DISPLACEMENT   = _fv("SB_DISPLACEMENT", 30.0)
SB_RET_MAX_BARS   = _iv("SB_RET_MAX_BARS", 20)
INTERNAL_SWEEP_PRIO = _iv("SB_INTERNAL_SWEEP_PRIO", 0)
WINDOW_START      = dt.time(9,59,0)
WINDOW_END        = dt.time(11,0,0)

def _in_window(ts_ms:int) -> bool:
    t = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET)
    return WINDOW_START <= t.time() <= WINDOW_END

def _iso(ts_ms:int) -> str:
    return dt.datetime.fromtimestamp(ts_ms/1000, tz=ET).strftime("%H:%M:%S")

class SBEngine:
    #
    # Silver Bullet strategy core
    #
    # We track THREE rolling bars:
    #   A (most recent closed minute)
    #   B (1 minute back)
    #   C (2 minutes back) ← internal sweep checks use this
    #
    # NEW intraminute logic:
    #   - A ALWAYS contains the "current minute" updated every tick
    #   - C always initialized to dict at minute start (not None)
    #   - No NoneType errors, immediate 1-second evals
    #

    def __init__(self, levels:dict):
        self.levels = levels or {}

        # Rolling minute structure (Option B)
        self._current_minute_bucket = None
        self._i = 0

        self._A = None
        self._B = None
        self._C = None

        # sweep memory
        self._pre_lo = None
        self._pre_hi = None

        from sbwatch import notify   # Discord send
        self._notify = notify.post_entry

    # ------------ internal helpers ------------

    def _update_prelo_prehi(self, ts, h, l):
        # optional pre-internal sweep
        if INTERNAL_SWEEP_PRIO:
            if self._pre_hi is None or h > self._pre_hi:
                self._pre_hi = h
            if self._pre_lo is None or l < self._pre_lo:
                self._pre_lo = l

    def _sweep_high(self, h):
        L = self.levels
        return ((h > L.get("pdh")) or (h > L.get("asia_high")) or
                (h > L.get("london_high")) or
                (INTERNAL_SWEEP_PRIO and self._pre_hi is not None and h > self._pre_hi))

    def _sweep_low(self, l):
        L = self.levels
        return ((l < L.get("pdl")) or (l < L.get("asia_low")) or
                (l < L.get("london_low")) or
                (INTERNAL_SWEEP_PRIO and self._pre_lo is not None and l < self._pre_lo))

    def _displacement(self, o:float, h:float, l:float, c:float) -> float:
        body = abs(c-o)
        rng  = max(h, o) - min(l, o)
        if rng == 0: return 0.0
        return body / rng   # ratio 0.0 - 1.0

    # ---------------------------------------------------------
    # ✅ MAIN ENTRY (called every tick live or every row replay)
    # ---------------------------------------------------------
    def on_bar(self, ts_ms:int, o:float, h:float, l:float, c:float):
        bucket = ts_ms // 60000     # minute grouping ID

        # -------- FIRST BAR OF THE DAY --------
        if self._current_minute_bucket is None:
            self._current_minute_bucket = bucket
            d = {"ts":ts_ms, "o":o, "h":h, "l":l, "c":c}
            self._A = d
            self._B = d.copy()
            self._C = d.copy()   # ✅ Option B — initialized immediately
            return

        # -------- INTRAMINUTE UPDATE (same minute) --------
        if bucket == self._current_minute_bucket:
            self._A["h"] = max(self._A["h"], h)
            self._A["l"] = min(self._A["l"], l)
            self._A["c"] = c
            return

        # -------- NEW MINUTE ARRIVED (roll A→B→C) --------
        self._current_minute_bucket = bucket
        self._i += 1

        self._C = self._B.copy()
        self._B = self._A.copy()
        self._A = {"ts":ts_ms, "o":o, "h":h, "l":l, "c":c}

        # -------- STRATEGY EVAL (entry only on new minute) --------
        A,B,C = self._A, self._B, self._C

        displacement = self._displacement(B["o"], B["h"], B["l"], B["c"])
        sweep_hi = self._sweep_high(C["h"])
        sweep_lo = self._sweep_low(C["l"])
        in_window = _in_window(ts_ms)

        if displacement >= SB_DISPLACEMENT/100 and in_window:
            direction = "LONG" if sweep_lo else ("SHORT" if sweep_hi else None)
            if direction:
                price = C["c"]
                sl = C["l"] if direction=="LONG" else C["h"]
                tp = price + SB_TP_RR*(price-sl) if direction=="LONG" else price - SB_TP_RR*(sl-price)

                payload = {
                    "side": direction,
                    "entry": float(price),
                    "sl": float(sl),
                    "tp": float(tp),
                    "when": ts_ms,
                    "label": "SB"
                }
                self._notify(payload)

        return  # done
