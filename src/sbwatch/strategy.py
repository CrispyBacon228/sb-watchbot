from __future__ import annotations
import os
import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional, Callable, Any

# --- runtime config (env overrides) ---
SB_TP_RR = float(os.environ.get("SB_TP_RR", "1.0"))
SB_SL_BUFFER = float(os.environ.get("SB_SL_BUFFER", "5.0"))

def _f(v: str, d: float) -> float:
    try:
        return float(os.environ.get(v, d))
    except Exception:
        return float(d)

def _i(v: str, d: int) -> int:
    try:
        return int(os.environ.get(v, d))
    except Exception:
        return int(d)

def _b(v: str, d="0") -> bool:
    return os.environ.get(v, d) in ("1", "true", "TRUE", "yes", "Yes")

def _t(str_hm: Optional[str], default: dt.time) -> dt.time:
    if not str_hm:
        return default
    return dt.time.fromisoformat(str_hm)

# Behavior toggles
FVG_MODE = os.environ.get("FVG_MODE", "3C").upper()          # "3C" or "2C"
SB_FVG_MIN = _f("SB_FVG_MIN", 0.15)                          # points
SB_DISPLACEMENT_MIN = _f("SB_DISPLACEMENT_MIN", 0.30)        # body/range ratio threshold (0..1)
SB_RET_MAX_BARS = _i("SB_RET_MAX_BARS", 20)
INTERNAL_SWEEP_PRE10 = _b("INTERNAL_SWEEP_PRE10", "1")
WINDOW_START = _t(os.environ.get("WINDOW_START", "10:00"), dt.time(0, 0))
WINDOW_END = _t(os.environ.get("WINDOW_END", "11:00"), dt.time(23, 59, 59))

# timezone: try America/New_York but fall back gracefully
try:
    ET = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:
    try:
        ET = ZoneInfo(os.environ.get("TZ", "UTC"))
    except Exception:
        ET = dt.timezone.utc

def _in_entry_window(ts_ms: int) -> bool:
    """Return True if timestamp falls inside the configured entry window (inclusive)."""
    t = dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=ET).time()
    return WINDOW_START <= t <= WINDOW_END

_in_window = _in_entry_window  # backwards compat

def _iso(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=ET).isoformat(timespec="seconds")


class SBEngine:
    """
    Silver Bullet strategy engine (1-second friendly).

    Intraminute approach:

      - A represents the current-minute bar and is updated on every tick.
      - B represents the previous finished minute (bar i-1).
      - C represents bar i-2.

    FVGs are created only on fully closed 1m candles (like the old engine),
    but returns into those FVGs are checked *every tick* using the current
    intraminute A-bar snapshot, so alerts go out immediately when the level
    is first hit.
    """

    def __init__(self, levels: dict):
        self.levels = levels or {}

        # rolling minute bookkeeping
        self._current_minute_bucket: Optional[int] = None
        self._i: int = 0  # synthetic "bar index" for SB_RET_MAX_BARS tracking

        # rolling 3-bar window (minute-level)
        self._A: Optional[dict] = None  # current minute (intraminute-aggregated)
        self._B: Optional[dict] = None  # prev finished minute
        self._C: Optional[dict] = None  # prev-prev finished minute

        # last FVGs
        self._last_bull: Optional[dict] = None
        self._last_bear: Optional[dict] = None

        # internal sweep memory for pre-10 AM
        self._pre_hi: Optional[float] = None
        self._pre_lo: Optional[float] = None

        # notify hook (module or callable)
        self._notify: Optional[Any] = None
        self._resolve_notify_from_env()
        self._notify_callable: Optional[Callable[..., Any]] = None
        self._resolve_notify_callable()

    # ----- notify resolution helpers -----

    def _resolve_notify_from_env(self):
        """Try to resolve sbwatch.notify.post_entry or fallback to a dummy printer."""
        try:
            import sbwatch.notify as _notify_mod
            if hasattr(_notify_mod, "post_entry") and callable(getattr(_notify_mod, "post_entry")):
                self._notify = _notify_mod.post_entry
            elif callable(_notify_mod):
                self._notify = _notify_mod
            else:
                self._notify = _notify_mod
        except Exception:
            def _fallback_notify(**kw):
                print("[ENTRY-FAKE]", kw)
            self._notify = _fallback_notify

    def _resolve_notify_callable(self):
        """Resolve self._notify into a callable if possible (function or object.post_entry)."""
        try:
            if callable(self._notify):
                self._notify_callable = self._notify
            elif hasattr(self._notify, "post_entry") and callable(getattr(self._notify, "post_entry")):
                self._notify_callable = getattr(self._notify, "post_entry")
            else:
                self._notify_callable = None
        except Exception:
            self._notify_callable = None

    # ----- pre-10 internal swing tracking -----

    def _update_pre10(self, ts_ms: int, h: float, l: float):
        if not INTERNAL_SWEEP_PRE10:
            return
        t = dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=ET)
        if t.hour < 10:
            if self._pre_hi is None or h > self._pre_hi:
                self._pre_hi = h
            if self._pre_lo is None or l < self._pre_lo:
                self._pre_lo = l

    def _swept_high(self, h: float) -> bool:
        L = self.levels
        return ((L.get("pdh") is not None and h > L.get("pdh")) or
                (L.get("asia_high") is not None and h > L.get("asia_high")) or
                (L.get("london_high") is not None and h > L.get("london_high")) or
                (INTERNAL_SWEEP_PRE10 and self._pre_hi is not None and h > self._pre_hi))

    def _swept_low(self, l: float) -> bool:
        L = self.levels
        return ((L.get("pdl") is not None and l < L.get("pdl")) or
                (L.get("asia_low") is not None and l < L.get("asia_low")) or
                (L.get("london_low") is not None and l < L.get("london_low")) or
                (INTERNAL_SWEEP_PRE10 and self._pre_lo is not None and l < self._pre_lo))

    def _displacement(self, o: float, h: float, l: float, c: float) -> float:
        rng = max(1e-9, h - l)
        body = abs(c - o)
        return body / rng

    # ----- robust posting to notify (works with multiple signatures) -----

    def _maybe_post(self, ts_ms: int, side: str, price: float, **extra):
        if not _in_entry_window(ts_ms):
            return

        payload = dict(
            side=side.upper(),
            entry=float(price),
            sl=float(extra.get("sl", 0.0)) if extra.get("sl") is not None else 0.0,
            tp=float(extra["tp"]) if extra.get("tp") is not None else None,
            sweep_label=str(extra.get("disp") or extra.get("label") or extra.get("mode") or "SB"),
            when=ts_ms,
        )

        if self._notify_callable is not None:
            try:
                self._notify_callable(**payload)
                return
            except TypeError:
                pass
            except Exception as e:
                print("[SBEngine] notify callable failed:", e)

        if callable(self._notify):
            try:
                self._notify(**payload)
                return
            except Exception as e:
                print("[SBEngine] raw notify failed:", e)

        print("[ENTRY]", payload, "iso:", _iso(ts_ms))

    # ----- shared return checker (used intraminute + on minute close) -----

    def _check_returns(self, C: dict, swept_hi: bool, swept_lo: bool, current_index: int, ts_ms: int):
        # LONG: return into last bull gap
        if self._last_bull:
            last = self._last_bull
            if ((current_index - last["i"]) <= SB_RET_MAX_BARS
                and C["l"] <= last["gap_top"] <= C["h"]
                and swept_lo):
                entry = last["gap_top"]
                sl = (last.get("c1_low", last.get("gap_bot")) - SB_SL_BUFFER)
                tp = entry + (entry - sl) * SB_TP_RR
                self._maybe_post(ts_ms, "LONG", entry, sl=sl, tp=tp,
                                 disp=last.get("disp"), mode=FVG_MODE)
                self._last_bull = None

        # SHORT: return into last bear gap
        if self._last_bear:
            last = self._last_bear
            if ((current_index - last["i"]) <= SB_RET_MAX_BARS
                and C["l"] <= last["gap_bot"] <= C["h"]
                and swept_hi):
                entry = last["gap_bot"]
                sl = (last.get("c1_high", last.get("gap_top")) + SB_SL_BUFFER)
                tp = entry - (sl - entry) * SB_TP_RR
                self._maybe_post(ts_ms, "SHORT", entry, sl=sl, tp=tp,
                                 disp=last.get("disp"), mode=FVG_MODE)
                self._last_bear = None

    # --------- main loop (1-second friendly, intraminute returns) ---------

    def on_bar(self, ts_ms: int, o: float, h: float, l: float, c: float):
        """
        Called with tick-level or bar-level OHLC updates.

        - New minute: build FVGs from three *completed* minutes and also check
          returns on the completed bar (C0).
        - Same minute: update A intraminute and check returns immediately
          against the current A snapshot.
        """
        minute_bucket = ts_ms // 60000

        # first tick ever
        if self._current_minute_bucket is None:
            self._current_minute_bucket = minute_bucket
            d = {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
            self._A = d.copy()
            self._B = d.copy()
            self._C = d.copy()
            self._i = 0
            self._pre_hi = None
            self._pre_lo = None
            self._update_pre10(ts_ms, h, l)
            return

        # -------- SAME-MINUTE TICK: intraminute returns --------
        if minute_bucket == self._current_minute_bucket:
            if self._A is None:
                self._A = {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
            else:
                self._A["h"] = max(self._A.get("h", h), h)
                self._A["l"] = min(self._A.get("l", l), l)
                self._A["c"] = c
                self._A["ts"] = ts_ms

            self._update_pre10(ts_ms, h, l)

            # use current A snapshot as "C" for return purposes
            C_intr = self._A
            swept_hi = self._swept_high(C_intr["h"])
            swept_lo = self._swept_low(C_intr["l"])

            # treat this as the "next" bar index after the last completed one
            current_index = self._i + 1 if self._i > 0 else 0
            self._check_returns(C_intr, swept_hi, swept_lo, current_index, ts_ms)
            return

        # -------- NEW MINUTE: build FVGs + returns on completed bar --------
        prevA = self._A.copy() if self._A else {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
        prevB = self._B.copy() if self._B else prevA.copy()
        prevC = self._C.copy() if self._C else prevB.copy()

        self._current_minute_bucket = minute_bucket
        self._i += 1

        # reconstruct original 1m triple: A0 (i-2), B0 (i-1), C0 (i)
        A0 = prevC
        B0 = prevB
        C0 = prevA

        self._update_pre10(C0["ts"], C0["h"], C0["l"])

        # --- FVG creation on completed minutes (same as old 1m behavior) ---
        disp_ref = None
        if FVG_MODE == "3C" and B0:
            disp_ref = self._displacement(B0["o"], B0["h"], B0["l"], B0["c"])
        elif FVG_MODE != "3C":
            disp_ref = self._displacement(C0["o"], C0["h"], C0["l"], C0["c"])

        if disp_ref is not None:
            disp_ok = disp_ref >= SB_DISPLACEMENT_MIN

            if disp_ok:
                if FVG_MODE == "3C" and A0:
                    # bullish 3C FVG: C0.low > A0.high
                    if (C0["l"] - A0["h"]) >= SB_FVG_MIN:
                        self._last_bull = {
                            "i": self._i,
                            "gap_top": C0["l"],
                            "gap_bot": A0["h"],
                            "disp": disp_ref,
                            "c1_low": A0["l"],
                            "c1_high": A0["h"],
                        }
                    # bearish 3C FVG: A0.low > C0.high
                    if (A0["l"] - C0["h"]) >= SB_FVG_MIN:
                        self._last_bear = {
                            "i": self._i,
                            "gap_top": A0["l"],
                            "gap_bot": C0["h"],
                            "disp": disp_ref,
                            "c1_low": A0["l"],
                            "c1_high": A0["h"],
                        }
                elif FVG_MODE != "3C" and B0:
                    # 2C variant: B0 acts as C1
                    if (C0["l"] - B0["h"]) >= SB_FVG_MIN:
                        self._last_bull = {
                            "i": self._i,
                            "gap_top": C0["l"],
                            "gap_bot": B0["h"],
                            "disp": disp_ref,
                            "c1_low": B0["l"],
                            "c1_high": B0["h"],
                        }
                    if (B0["l"] - C0["h"]) >= SB_FVG_MIN:
                        self._last_bear = {
                            "i": self._i,
                            "gap_top": B0["l"],
                            "gap_bot": C0["h"],
                            "disp": disp_ref,
                            "c1_low": B0["l"],
                            "c1_high": B0["h"],
                        }

        # sweeps & returns on the completed bar C0 (minute-close behaviour)
        swept_hi = self._swept_high(C0["h"])
        swept_lo = self._swept_low(C0["l"])
        # MINUTE-CLOSE RETURNS DISABLED

        # self._check_returns(C0, swept_hi, swept_lo, self._i, C0["ts"])

        # roll window forward & seed A with new minute first tick
        self._C = prevB
        self._B = prevA
        self._A = {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
        return
