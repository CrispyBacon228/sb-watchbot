from __future__ import annotations
import os, datetime as dt
from zoneinfo import ZoneInfo

# Public API expected by the rest of your app:
# - class SBEngine(levels: dict)
# - method on_bar(ts_ms:int, o:float, h:float, l:float, c:float)
# - calls sbwatch.notify.post_entry(...) when an entry qualifies

ET = ZoneInfo("America/New_York")

def _f(v, d): 
    try: return float(os.environ.get(v, d))
    except: return float(d)

def _i(v, d):
    try: return int(os.environ.get(v, d))
    except: return int(d)

def _b(v, d="0"):
    return os.environ.get(v, d) in ("1","true","TRUE","yes","Yes")

def _t(str_hm: str|None, default: dt.time) -> dt.time:
    if not str_hm: return default
    return dt.time.fromisoformat(str_hm)

FVG_MODE             = os.environ.get("FVG_MODE", "3C").upper()            # "3C" (default) or "2C"
SB_FVG_MIN           = _f("SB_FVG_MIN", "0.15")                            # gap size in points
SB_DISPLACEMENT_MIN  = _f("SB_DISPLACEMENT_MIN", "0.30")                   # body/range threshold
SB_RET_MAX_BARS      = _i("SB_RET_MAX_BARS", "20")                         # return must occur within N bars
INTERNAL_SWEEP_PRE10 = _b("INTERNAL_SWEEP_PRE10", "1")                     # default ON to match probes
WINDOW_START         = _t(os.environ.get("WINDOW_START", "10:00"), dt.time(0,0))
WINDOW_END           = _t(os.environ.get("WINDOW_END",   "11:00"), dt.time(23,59,59))

def _in_entry_window(ts_ms:int)->bool:
    t = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET).time()
    return WINDOW_START <= t <= WINDOW_END

def _iso(ts_ms:int)->str:
    return dt.datetime.fromtimestamp(ts_ms/1000, tz=ET).strftime("%H:%M:%S")

class SBEngine:
    """
    Probe-parity strategy engine:
      - 3C FVG (default): displacement on bar B; bullish if C.low > A.high; bearish if A.low > C.high
      - 2C FVG (optional via FVG_MODE=2C): displacement on current C; bullish if C.low > B.high; bearish if B.low > C.high
      - Sweeps: PDH/PDL, Asia high/low, London high/low, plus optional pre-10 internal swing
      - Returns: entry on first return into the FVG within SB_RET_MAX_BARS bars
      - Entries-only time gate: only post entries if the *entry bar* is within WINDOW_START..WINDOW_END
    """
    def __init__(self, levels: dict):
        self.levels = levels or {}
        # rolling bars
        self._A = None   # bar i-2
        self._B = None   # bar i-1
        self._i = 0
        # last FVGs
        self._last_bull = None
        self._last_bear = None
        # pre-10 swings
        self._pre_hi = None
        self._pre_lo = None
        # post hook
        try:
            from sbwatch import notify
        except Exception:
            # fallback if used outside package
            class _N: 
                @staticmethod
                def post_entry(**kw): 
                    print("[ENTRY]", kw)
            notify = _N()
        self._notify = notify

    # --------- helpers ---------

    def _update_pre10(self, ts_ms:int, h:float, l:float):
        if not INTERNAL_SWEEP_PRE10: 
            return
        t = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET)
        if t.hour < 10:
            self._pre_hi = h if self._pre_hi is None or h > self._pre_hi else self._pre_hi
            self._pre_lo = l if self._pre_lo is None or l < self._pre_lo else self._pre_lo

    def _swept_high(self, h:float) -> bool:
        L = self.levels
        return ((L.get("pdh") and h > L["pdh"]) or
                (L.get("asia_high") and h > L["asia_high"]) or
                (L.get("london_high") and h > L["london_high"]) or
                (INTERNAL_SWEEP_PRE10 and self._pre_hi is not None and h > self._pre_hi))

    def _swept_low(self, l:float) -> bool:
        L = self.levels
        return ((L.get("pdl") and l < L["pdl"]) or
                (L.get("asia_low") and l < L["asia_low"]) or
                (L.get("london_low") and l < L["london_low"]) or
                (INTERNAL_SWEEP_PRE10 and self._pre_lo is not None and l < self._pre_lo))

    def _displacement(self, o:float, h:float, l:float, c:float) -> float:
        rng = max(1e-9, h - l)
        body = abs(c - o)
        return body / rng

    def _maybe_post(self, ts_ms:int, side:str, price:float, **extra):
        # entries-only gate
        if not _in_entry_window(ts_ms):
            return
        # unify payload with existing webhook usage
        payload = dict(when=ts_ms, side=side.upper(), price=price)
        payload.update(extra)
        try:
            self._notify.post_entry(**payload)
        except TypeError:
            # older signature: notify.post_entry(ts=ts_ms, price=price, side=...)
            self._notify.post_entry(ts=ts_ms, price=price, side=side.upper(), **extra)

    # --------- main loop ---------

    def on_bar(self, ts_ms:int, o:float, h:float, l:float, c:float):
        """Feed one 1m bar; emits entry via notify when gates align."""
        self._i += 1

        # maintain pre-10 swings for sweep logic
        self._update_pre10(ts_ms, h, l)

        # roll bars
        A = self._A
        B = self._B
        C = dict(ts=ts_ms, o=o, h=h, l=l, c=c)

        # compute displacement on B (3C) or C (2C)
        disp_ref = None
        if FVG_MODE == "3C" and B:
            disp_ref = self._displacement(B["o"], B["h"], B["l"], B["c"])
        else:
            disp_ref = self._displacement(C["o"], C["h"], C["l"], C["c"])

        disp_ok = disp_ref >= SB_DISPLACEMENT_MIN

        # build (or refresh) FVGs when displacement is OK
        if disp_ok:
            if FVG_MODE == "3C" and A:
                # bullish FVG: C.low > A.high (+gap size ≥ SB_FVG_MIN)
                if (C["l"] - A["h"]) >= SB_FVG_MIN:
                    self._last_bull = dict(i=self._i, gap_top=C["l"], gap_bot=A["h"], disp=disp_ref)
                # bearish FVG: A.low > C.high
                if (A["l"] - C["h"]) >= SB_FVG_MIN:
                    self._last_bear = dict(i=self._i, gap_top=A["l"], gap_bot=C["h"], disp=disp_ref)
            elif FVG_MODE != "3C" and B:
                # 2C variant
                if (C["l"] - B["h"]) >= SB_FVG_MIN:
                    self._last_bull = dict(i=self._i, gap_top=C["l"], gap_bot=B["h"], disp=disp_ref)
                if (B["l"] - C["h"]) >= SB_FVG_MIN:
                    self._last_bear = dict(i=self._i, gap_top=B["l"], gap_bot=C["h"], disp=disp_ref)

        # sweep checks (on current bar)
        swept_hi = self._swept_high(C["h"])
        swept_lo = self._swept_low(C["l"])

        # returns into last FVG within window of bars
        if self._last_bull:
            last = self._last_bull
            if (self._i - last["i"]) <= SB_RET_MAX_BARS and C["l"] <= last["gap_top"] and swept_lo:
                # LONG entry at gap top (or current close; using gap top keeps parity with probe print)
                self._maybe_post(C["ts"], "LONG", last["gap_top"], disp=last["disp"], mode=FVG_MODE)
                self._last_bull = None

        if self._last_bear:
            last = self._last_bear
            if (self._i - last["i"]) <= SB_RET_MAX_BARS and C["h"] >= last["gap_bot"] and swept_hi:
                self._maybe_post(C["ts"], "SHORT", last["gap_bot"], disp=last["disp"], mode=FVG_MODE)
                self._last_bear = None

        # advance rolling window
        self._A = B
        self._B = C
