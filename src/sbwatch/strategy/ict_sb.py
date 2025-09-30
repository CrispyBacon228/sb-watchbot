from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Literal
import pytz
import pandas as pd
from sbwatch.levels.asia import asia_high_low_from_df

NY = pytz.timezone("America/New_York")

@dataclass
class Signal:
    side: str                 # "LONG" or "SHORT"
    price: float              # proposed entry (FVG return or touch)
    asia_high: float
    asia_low: float
    fvg_top: float            # for LONG: FVG upper; for SHORT: lower
    fvg_bot: float            # for LONG: FVG lower; for SHORT: upper
    basis_ts: pd.Timestamp    # displacement candle timestamp

@dataclass
class Explain:
    in_window: bool
    asia_high: Optional[float]
    asia_low: Optional[float]
    displaced_up: bool
    displaced_down: bool
    disp_value: float
    fvg_ok: bool
    price_in_fvg: bool
    entry_mode: str
    reason: str

@dataclass
class TradeResult:
    side: str
    entry_ts: pd.Timestamp
    entry: float
    stop: float
    tp: float
    exit_ts: pd.Timestamp
    exit_price: float
    outcome: str  # "TP" | "SL" | "TIMEOUT"

def in_ny_10_11(dt: datetime) -> bool:
    local = dt.astimezone(NY)
    return local.hour == 10

def _asia_levels(df: pd.DataFrame, now: datetime) -> Tuple[Optional[float], Optional[float]]:
    return asia_high_low_from_df(df, now, tz="America/New_York")

def _displacement(bar: pd.Series) -> float:
    rng = max(1e-6, float(bar["high"]) - float(bar["low"]))
    body = abs(float(bar["close"]) - float(bar["open"]))
    return body / rng

def _fvg_bull(df: pd.DataFrame, i: int) -> Optional[Tuple[float,float]]:
    if i < 2: return None
    h2 = float(df.iloc[i-2]["high"])
    l0 = float(df.iloc[i]["low"])
    if l0 > h2:
        return (h2, l0)
    return None

def _fvg_bear(df: pd.DataFrame, i: int) -> Optional[Tuple[float,float]]:
    if i < 2: return None
    h0 = float(df.iloc[i]["high"])
    l2 = float(df.iloc[i-2]["low"])
    if h0 < l2:
        return (l2, h0)  # return as (top>bot)
    return None

def detect_signal_strict(
    df: pd.DataFrame, now: datetime, *,
    disp_min: float = 0.60,
    require_fvg: bool = True,
    entry_mode: Literal["fvg_return","touch"] = "fvg_return",
    explain: bool = False
) -> Optional[Signal] | Tuple[Optional[Signal], Explain]:
    """
    ICT-esque SB detector:
    - 10–11 NY window
    - displacement through Asia H/L on prior bar
    - optional FVG requirement
    - entry either on FVG return ("fvg_return") or immediate touch break ("touch")
    """
    info = Explain(False, None, None, False, False, 0.0, False, False, entry_mode, "")
    if df.empty or len(df) < 5:
        info.reason = "not_enough_bars"
        return (None, info) if explain else None
    info.in_window = in_ny_10_11(now)
    if not info.in_window:
        info.reason = "outside_10_11"
        return (None, info) if explain else None

    ah, al = _asia_levels(df, now)
    info.asia_high, info.asia_low = ah, al
    if ah is None or al is None:
        info.reason = "asia_levels_missing"
        return (None, info) if explain else None

    i = len(df) - 1
    prev = df.iloc[i-1]
    cur  = df.iloc[i]
    info.disp_value = _displacement(prev)

    # LONG case
    if float(prev["close"]) > ah >= float(prev["open"]) and info.disp_value >= disp_min:
        info.displaced_up = True
        fvg = _fvg_bull(df, i-1)
        if require_fvg and not fvg:
            info.reason = "no_bull_fvg"
            return (None, info) if explain else None
        top, bot = (fvg if fvg else (ah, ah))
        info.fvg_ok = fvg is not None or not require_fvg
        price = float(cur["close"])
        info.price_in_fvg = (bot <= price <= top)
        if entry_mode == "fvg_return" and not info.price_in_fvg:
            info.reason = "not_in_fvg"
            return (None, info) if explain else None
        return (Signal("LONG", price, ah, al, top, bot, prev["timestamp"]), info) if explain \
               else Signal("LONG", price, ah, al, top, bot, prev["timestamp"])

    # SHORT case
    if float(prev["close"]) < al <= float(prev["open"]) and info.disp_value >= disp_min:
        info.displaced_down = True
        fvg = _fvg_bear(df, i-1)
        if require_fvg and not fvg:
            info.reason = "no_bear_fvg"
            return (None, info) if explain else None
        top, bot = (fvg if fvg else (al, al))
        info.fvg_ok = fvg is not None or not require_fvg
        price = float(cur["close"])
        info.price_in_fvg = (bot <= price <= top)
        if entry_mode == "fvg_return" and not info.price_in_fvg:
            info.reason = "not_in_fvg"
            return (None, info) if explain else None
        return (Signal("SHORT", price, ah, al, top, bot, prev["timestamp"]), info) if explain \
               else Signal("SHORT", price, ah, al, top, bot, prev["timestamp"])

    info.reason = "no_displacement_through_asia"
    return (None, info) if explain else None

def simulate_trade(df: pd.DataFrame, idx_entry: int, sig: Signal, rr: float = 2.0, max_minutes: int = 120) -> TradeResult:
    entry_ts = df.iloc[idx_entry]["timestamp"]
    entry = float(df.iloc[idx_entry]["close"])
    if sig.side == "LONG":
        stop = min(sig.fvg_bot, sig.asia_low)
        risk = max(1e-6, entry - stop)
        tp = entry + rr * risk
    else:
        stop = max(sig.fvg_top, sig.asia_high)
        risk = max(1e-6, stop - entry)
        tp = entry - rr * risk

    end_idx = min(len(df)-1, idx_entry + max_minutes)
    for j in range(idx_entry+1, end_idx+1):
        bar = df.iloc[j]
        high, low = float(bar["high"]), float(bar["low"])
        if sig.side == "LONG":
            if low <= stop:
                return TradeResult(sig.side, entry_ts, entry, stop, tp, bar["timestamp"], stop, "SL")
            if high >= tp:
                return TradeResult(sig.side, entry_ts, entry, stop, tp, bar["timestamp"], tp, "TP")
        else:
            if high >= stop:
                return TradeResult(sig.side, entry_ts, entry, stop, tp, bar["timestamp"], stop, "SL")
            if low <= tp:
                return TradeResult(sig.side, entry_ts, entry, stop, tp, bar["timestamp"], tp, "TP")
    lastbar = df.iloc[end_idx]
    return TradeResult(sig.side, entry_ts, entry, stop, tp, lastbar["timestamp"], float(lastbar["close"]), "TIMEOUT")
