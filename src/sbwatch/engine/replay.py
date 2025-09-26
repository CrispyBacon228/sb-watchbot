from __future__ import annotations
import os, csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from loguru import logger
from sbwatch.core.levels import load_levels
from sbwatch.adapters.databento import ohlcv_range, clamp_end
from sbwatch.adapters.csvsource import iter_ohlcv_from_csv

DATASET = os.getenv("DB_DATASET", "GLBX.MDP3")
SCHEMA  = os.getenv("DB_SCHEMA",  "ohlcv-1m")
SYMBOL  = os.getenv("FRONT_SYMBOL")
LEVELS_PATH = os.getenv("LEVELS_PATH", "./data/levels.json")
DIV = int(os.getenv("PRICE_DIVISOR", "1000000000"))
TICK_SIZE = float(os.getenv("TICK_SIZE", "0.25"))
TOL_TICKS = int(os.getenv("TOL_TICKS", "4"))
TOL = TICK_SIZE * TOL_TICKS

def _rows_for_et_date(et_date: str):
    from zoneinfo import ZoneInfo
    TZ_ET = ZoneInfo("America/New_York")
    y,m,d = map(int, et_date.split("-"))
    s_et = datetime(y,m,d,0,0,tzinfo=TZ_ET)
    e_et = s_et + timedelta(days=1)
    s_utc = s_et.astimezone(timezone.utc)
    e_utc = e_et.astimezone(timezone.utc)
    e_utc = clamp_end(e_utc)
    return list(ohlcv_range(DATASET, SCHEMA, SYMBOL, s_utc, e_utc))

def _hlc_scaled_from_dbn(r):
    h = getattr(r,"high", getattr(r,"h",None))
    l = getattr(r,"low",  getattr(r,"l",None))
    c = getattr(r,"close",getattr(r,"c",None))
    if c is None:
        c = (float(h)+float(l))/2.0
    return float(h)/DIV, float(l)/DIV, float(c)/DIV

def _signal_row(ts: datetime, name: str, price: float, level: float):
    return [ts.isoformat(), name, f"{price:.2f}", f"{level:.2f}"]

def run_replay(date_et: str, out_dir: str = "./out", csv_path: Optional[str] = None,
               wick_only: bool = True) -> str:
    """
    Replay a day and write alerts to CSV. Returns the output file path.
    - If csv_path is given, read that. Otherwise, fetch from Databento Historical.
    - Uses same wick logic as live. Cooldowns are not applied.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = str(Path(out_dir) / f"replay_{date_et}.csv")

    lv = load_levels(LEVELS_PATH)
    rows_csv = []

    if csv_path:
        rows = list(iter_ohlcv_from_csv(csv_path))
        for r in rows:
            h,l,c = float(r["high"]), float(r["low"]), float(r["close"])
            ts = r["time"]
            rows_csv.append((ts, h, l, c))
    else:
        dbn = _rows_for_et_date(date_et)
        ts = None
        cur_min = None
        for r in dbn:
            ts_attr = getattr(r, "ts_recv", None) or getattr(r, "ts_event", None) or None
            if ts_attr:
                try:
                    ts = datetime.fromtimestamp(float(ts_attr)/1e9, tz=timezone.utc)
                except Exception:
                    ts = None
            h,l,c = _hlc_scaled_from_dbn(r)
            if ts is None:
                if cur_min is None:
                    cur_min = datetime.now(timezone.utc)
                else:
                    cur_min += timedelta(minutes=1)
                ts_use = cur_min
            else:
                ts_use = ts
            rows_csv.append((ts_use, h, l, c))

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_utc","signal","price","level"])

        prev_price = None
        for ts,h,l,c in rows_csv:
            signals = []
            if h >= lv.pdh + TOL and c < lv.pdh:               signals.append(("PDH_REJECT", lv.pdh))
            if l <= lv.pdl - TOL and c > lv.pdl:               signals.append(("PDL_REJECT", lv.pdl))
            if h >= lv.asia_high + TOL and c < lv.asia_high:   signals.append(("ASIA_H_REJECT", lv.asia_high))
            if l <= lv.asia_low  - TOL and c > lv.asia_low:    signals.append(("ASIA_L_REJECT", lv.asia_low))
            if h >= lv.london_high + TOL and c < lv.london_high: signals.append(("LON_H_REJECT", lv.london_high))
            if l <= lv.london_low  - TOL and c > lv.london_low:  signals.append(("LON_L_REJECT", lv.london_low))

            if not wick_only and prev_price is not None:
                def _up(p,cur,lvl):   return p < lvl <= cur
                def _down(p,cur,lvl): return p > lvl >= cur
                if _up(prev_price,c,lv.pdh):  signals.append(("PDH_UP", lv.pdh))
                if _down(prev_price,c,lv.pdh):signals.append(("PDH_DOWN", lv.pdh))
                if _up(prev_price,c,lv.pdl):  signals.append(("PDL_UP", lv.pdl))
                if _down(prev_price,c,lv.pdl):signals.append(("PDL_DOWN", lv.pdl))

            for name, lvlval in signals:
                w.writerow(_signal_row(ts, name, c, lvlval))

            prev_price = c

    logger.info("Replay complete → {}", out_path)
    return out_path
