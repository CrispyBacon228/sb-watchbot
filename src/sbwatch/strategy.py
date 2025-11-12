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
    # fallback: use system local tz or UTC if missing
    try:
        ET = ZoneInfo(os.environ.get("TZ", "UTC"))
    except Exception:
        ET = dt.timezone.utc

def _in_entry_window(ts_ms: int) -> bool:
    """Return True if timestamp falls inside the configured entry window (inclusive)."""
    t = dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=ET).time()
    return WINDOW_START <= t <= WINDOW_END

# older code may refer to _in_window; alias for compatibility
_in_window = _in_entry_window

def _iso(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=ET).strftime("%H:%M:%S")

class SBEngine:
    """
    Silver Bullet strategy engine (1-second friendly).

    Intraminute approach:
      - A always represents the current-minute bar and is updated on every tick.
      - B represents the previous finished minute (bar i-1).
      - C represents bar i-2 (used for sweep checks, etc.) and is initialized to a dict
        immediately on first minute so C is never None.
    """

    def __init__(self, levels: dict):
        self.levels = levels or {}

        # rolling minute bookkeeping
        self._current_minute_bucket: Optional[int] = None
        self._i = 0  # bar index / counter

        self._A: Optional[dict] = None
        self._B: Optional[dict] = None
        self._C: Optional[dict] = None

        # sweep memory pre-10
        self._pre_hi: Optional[float] = None
        self._pre_lo: Optional[float] = None

        # last FVGs (for return detection)
        self._last_bull: Optional[dict] = None
        self._last_bear: Optional[dict] = None

        # notify - try to import from package
        try:
            # package exposes a notify module with post_entry
            from sbwatch import notify as _notify_mod  # type: ignore
            # allow both module.post_entry or module itself (callable)
            if hasattr(_notify_mod, "post_entry") and callable(getattr(_notify_mod, "post_entry")):
                self._notify = _notify_mod.post_entry
            elif callable(_notify_mod):
                self._notify = _notify_mod
            else:
                # keep module in case code expects object
                self._notify = _notify_mod
        except Exception:
            # fallback: provide a simple printer to avoid crashing in dev/test env
            def _fallback_notify(**kw):
                print("[ENTRY-FAKE]", kw)
            self._notify = _fallback_notify

        # convenience: expose a resolved callable if possible
        self._notify_callable: Optional[Callable[..., Any]] = None
        self._resolve_notify_callable()

    def _resolve_notify_callable(self):
        """Resolve self._notify into a callable if possible (function or object.post_entry)."""
        try:
            if callable(self._notify):
                self._notify_callable = self._notify  # direct callable
            elif hasattr(self._notify, "post_entry") and callable(getattr(self._notify, "post_entry")):
                self._notify_callable = getattr(self._notify, "post_entry")
            else:
                self._notify_callable = None
        except Exception:
            self._notify_callable = None

    # ----- helpers for sweep/displacement -----

    def _update_pre10(self, ts_ms: int, h: float, l: float):
        """Collect pre-10 internal swing highs/lows (optional)."""
        if not INTERNAL_SWEEP_PRE10:
            return
        t = dt.datetime.fromtimestamp(ts_ms / 1000.0, tz=ET)
        if t.hour < 10:
            if self._pre_hi is None or h > self._pre_hi:
                self._pre_hi = h
            if self._pre_lo is None or l < self._pre_lo:
                self._pre_lo = l

    def _swept_high(self, h: float) -> bool:
        """Return True if h sweeps any configured high level (PDH, Asia, London or pre-10)."""
        L = self.levels
        return ((L.get("pdh") is not None and h > L.get("pdh")) or
                (L.get("asia_high") is not None and h > L.get("asia_high")) or
                (L.get("london_high") is not None and h > L.get("london_high")) or
                (INTERNAL_SWEEP_PRE10 and self._pre_hi is not None and h > self._pre_hi))

    def _swept_low(self, l: float) -> bool:
        """Return True if l sweeps any configured low level (PDL, Asia, London or pre-10)."""
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
        """
        Attempt to post an entry. This function is tolerant to different notify signatures:
         - Modern: notify.post_entry(side='LONG', entry=..., sl=..., tp=..., sweep_label=..., when=...)
         - Older positional: notify.post_entry(side, entry, sl, tp, sweep_label, when)
         - Minimal: notify.post_entry(side, entry)
        It will not raise on failure (prints to stderr) to avoid stopping the strategy loop.
        """
        # entries-only gate
        try:
            if not _in_entry_window(ts_ms):
                return
        except Exception:
            # if the window check fails unexpectedly, allow posting (safer for testing)
            pass

        payload = {
            "side": side.upper(),
            "entry": float(price),
            "sl": float(extra.get("sl", 0.0)) if isinstance(extra.get("sl", 0), (int, float, str)) else 0.0,
            "tp": (float(extra.get("tp")) if isinstance(extra.get("tp"), (int, float, str)) else None),
            "sweep_label": str(extra.get("disp") or extra.get("label") or extra.get("mode") or "SB"),
            "when": ts_ms,
        }

        # ensure we have a callable notifier
        notifier = self._notify_callable
        if notifier is None:
            # try resolving again (in case someone replaced self._notify)
            self._resolve_notify_callable()
            notifier = self._notify_callable

        # fallback to raw attribute if resolution failed
        if notifier is None:
            try:
                if callable(self._notify):
                    notifier = self._notify
                elif hasattr(self._notify, "post_entry") and callable(getattr(self._notify, "post_entry")):
                    notifier = getattr(self._notify, "post_entry")
            except Exception:
                notifier = None

        # final attempt to call notify in multiple ways
        try:
            if notifier is None:
                # as last resort if nothing resolved, try calling self._notify directly
                if callable(self._notify):
                    self._notify(**payload)
                    return
                elif hasattr(self._notify, "post_entry") and callable(getattr(self._notify, "post_entry")):
                    getattr(self._notify, "post_entry")(**payload)
                    return
                else:
                    raise RuntimeError("No callable notifier resolved")
            # try keyword style first
            notifier(**payload)
            return
        except TypeError:
            # positional fallback ordering: side, entry, sl, tp, sweep_label, when
            try:
                args = (
                    payload.get("side"),
                    payload.get("entry"),
                    payload.get("sl"),
                    payload.get("tp"),
                    payload.get("sweep_label"),
                    payload.get("when"),
                )
                notifier(*args)
                return
            except Exception:
                pass
            # minimal fallback
            try:
                notifier(payload.get("side"), payload.get("entry"))
                return
            except Exception:
                pass
        except Exception:
            # other unexpected exceptions - swallow but print for debugging
            import sys, traceback
            sys.stderr.write("Notifier call raised an unexpected exception:\n")
            traceback.print_exc(file=sys.stderr)
            return

        # if we reach here everything failed, print trace for debugging
        import sys, traceback
        sys.stderr.write("Notifier call failed for all fallback attempts. payload:\n")
        sys.stderr.write(repr(payload) + "\n")
        traceback.print_stack(file=sys.stderr)

    # ----- main entry: called on every tick (1s) or bar -----

    def on_bar(self, ts_ms: int, o: float, h: float, l: float, c: float):
        """
        Called with tick-level or bar-level OHLC updates.

        Behavior:
          - if this is the first tick ever, initialize A/B/C (C is not None).
          - if bucket (minute) == current, update A in place (intraminute).
          - if new minute arrived, roll A->B->C, increment counter, then run strategy eval using B and C.
        """
        minute_bucket = ts_ms // 60000

        # first bar/tick ever: initialize current minute bucket and all bars
        if self._current_minute_bucket is None:
            self._current_minute_bucket = minute_bucket
            d = {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
            self._A = d.copy()
            self._B = d.copy()
            self._C = d.copy()
            # maintain pre10 memory too
            self._update_pre10(ts_ms, h, l)
            return

        # intraminute update: update A and continue evaluating (we do not roll minute)
        if minute_bucket == self._current_minute_bucket:
            # update current minute A (expand high/low and set close)
            if self._A is None:
                self._A = {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
            else:
                self._A["h"] = max(self._A.get("h", h), h)
                self._A["l"] = min(self._A.get("l", l), l)
                self._A["c"] = c
                self._A["ts"] = ts_ms
            # update pre10 memory for sweep detection
            self._update_pre10(ts_ms, h, l)
            # do NOT run new-minute eval here (we only evaluate on roll)
            return

        # NEW minute arrived -> roll A -> B -> C
        self._current_minute_bucket = minute_bucket
        self._i += 1

        # Ensure copies to avoid accidental mutability
        prevA = self._A.copy() if self._A else {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}
        prevB = self._B.copy() if self._B else prevA.copy()

        # roll
        self._C = prevB
        self._B = prevA
        self._A = {"ts": ts_ms, "o": o, "h": h, "l": l, "c": c}

        # update pre10 memory with final C (or A/B)
        self._update_pre10(ts_ms, h, l)

        # -------- strategy evaluation (only on new minute roll) --------
        A, B, C = self._A, self._B, self._C

        # if we don't have B/C for any reason - skip
        if not B or not C:
            return

        # compute displacement on B for 3C mode or on C/B for 2C mode
        if FVG_MODE == "3C":
            disp_ref = self._displacement(B["o"], B["h"], B["l"], B["c"])
        else:
            # 2C uses current C as displacement reference (or B depending on convention)
            disp_ref = self._displacement(C["o"], C["h"], C["l"], C["c"])

        disp_ok = disp_ref >= SB_DISPLACEMENT_MIN

        # build/refresh last FVGs when displacement ok
        if disp_ok:
            if FVG_MODE == "3C" and A:
                # bullish: C.low > A.high by gap size
                if (C["l"] - A["h"]) >= SB_FVG_MIN:
                    self._last_bull = {
                        "i": self._i,
                        "gap_top": C["l"],
                        "gap_bot": A["h"],
                        "disp": disp_ref,
                        "c1_low": A["l"],
                        "c1_high": A["h"],
                    }
                # bearish: A.low > C.high
                if (A["l"] - C["h"]) >= SB_FVG_MIN:
                    self._last_bear = {
                        "i": self._i,
                        "gap_top": A["l"],
                        "gap_bot": C["h"],
                        "disp": disp_ref,
                        "c1_low": A["l"],
                        "c1_high": A["h"],
                    }
            elif FVG_MODE != "3C" and B:
                # 2C variant (B acts like C1)
                if (C["l"] - B["h"]) >= SB_FVG_MIN:
                    self._last_bull = {
                        "i": self._i,
                        "gap_top": C["l"],
                        "gap_bot": B["h"],
                        "disp": disp_ref,
                        "c1_low": B["l"],
                        "c1_high": B["h"],
                    }
                if (B["l"] - C["h"]) >= SB_FVG_MIN:
                    self._last_bear = {
                        "i": self._i,
                        "gap_top": B["l"],
                        "gap_bot": C["h"],
                        "disp": disp_ref,
                        "c1_low": B["l"],
                        "c1_high": B["h"],
                    }

        # sweep checks on current C (we use C for sweep memory)
        swept_hi = self._swept_high(C["h"])
        swept_lo = self._swept_low(C["l"])

        # check returns into last bull gap
        if self._last_bull:
            last = self._last_bull
            if (self._i - last["i"]) <= SB_RET_MAX_BARS and C["l"] <= last["gap_top"] and swept_lo and disp_ok:
                entry = last["gap_top"]
                sl = (last.get("c1_low", last.get("gap_bot")) - SB_SL_BUFFER)
                tp = entry + (entry - sl) * SB_TP_RR
                # attempt post
                self._maybe_post(C["ts"], "LONG", entry, sl=sl, tp=tp, disp=last.get("disp"), mode=FVG_MODE)
                self._last_bull = None

        # check returns into last bear gap
        if self._last_bear:
            last = self._last_bear
            if (self._i - last["i"]) <= SB_RET_MAX_BARS and C["h"] >= last["gap_bot"] and swept_hi and disp_ok:
                entry = last["gap_bot"]
                sl = (last.get("c1_high", last.get("gap_top")) + SB_SL_BUFFER)
                tp = entry - (sl - entry) * SB_TP_RR
                self._maybe_post(C["ts"], "SHORT", entry, sl=sl, tp=tp, disp=last.get("disp"), mode=FVG_MODE)
                self._last_bear = None

        # done (A already set to the new minute's initial OHLC)
        return
