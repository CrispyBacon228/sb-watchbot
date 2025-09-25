from __future__ import annotations
import os, typer
from datetime import datetime, timezone, timedelta
from loguru import logger
from sbwatch.core.sessions import (
    et_midnight, prev_business_day_midnight,
    et_window_to_utc_range, ASIA, LONDON, RTH
)
from sbwatch.core.levels import DayLevels, save_levels
from sbwatch.adapters.databento import ohlcv_range

app = typer.Typer(help="Build session levels (Asia, London, PDH/PDL).")

PRICE_DIVISOR = int(os.getenv("PRICE_DIVISOR", "1000000000"))  # default = 1e9

def _extract_hl(rec):
    if hasattr(rec, "high") and hasattr(rec, "low"):
        return float(rec.high), float(rec.low)
    if hasattr(rec, "h") and hasattr(rec, "l"):
        return float(rec.h), float(rec.l)
    if isinstance(rec, dict):
        if "high" in rec and "low" in rec:
            return float(rec["high"]), float(rec["low"])
        if "h" in rec and "l" in rec:
            return float(rec["h"]), float(rec["l"])
    raise TypeError(f"Unrecognized row type/fields: {type(rec)}")

def _hi_lo(rows):
    hi = None; lo = None; count = 0
    for r in rows:
        h, l = _extract_hl(r)
        hi = h if hi is None else max(hi, h)
        lo = l if lo is None else min(lo, l)
        count += 1
    return hi, lo, count

def _safe_hi_lo(dataset, schema, symbol, s_utc, e_utc):
    now_cut = datetime.now(timezone.utc) - timedelta(seconds=120)
    end = min(e_utc, now_cut)
    if end <= s_utc:
        return None, None, 0
    return _hi_lo(ohlcv_range(dataset, schema, symbol, s_utc, end))

@app.command("build")
def build_levels(
    date: str = typer.Option(None, help="ET date YYYY-MM-DD (default: today in ET)")
):
    dataset = os.getenv("DB_DATASET", "GLBX.MDP3")
    schema  = os.getenv("DB_SCHEMA",  "ohlcv-1m")
    symbol  = os.getenv("FRONT_SYMBOL")
    outpath = os.getenv("LEVELS_PATH", "./data/levels.json")
    if not symbol:
        raise typer.BadParameter("FRONT_SYMBOL missing in env (.env)")

    etD   = et_midnight(date)
    etD_1 = prev_business_day_midnight(etD)

    a_s, a_e = et_window_to_utc_range(etD_1, ASIA)
    l_s, l_e = et_window_to_utc_range(etD, LONDON)
    r_s, r_e = et_window_to_utc_range(etD_1, RTH)

    a_hi, a_lo, a_n = _safe_hi_lo(dataset, schema, symbol, a_s, a_e)
    l_hi, l_lo, l_n = _safe_hi_lo(dataset, schema, symbol, l_s, l_e)
    p_hi, p_lo, p_n = _safe_hi_lo(dataset, schema, symbol, r_s, r_e)

    if p_n == 0:
        logger.error("No RTH data for previous day — cannot compute PDH/PDL.")
        raise typer.Exit(code=2)

    if a_n == 0: a_hi, a_lo = p_hi, p_lo
    if l_n == 0: l_hi, l_lo = p_hi, p_lo

    # apply divisor
    def div(x): return round(x / PRICE_DIVISOR, 2) if x is not None else None

    lv = DayLevels(
        date_et = etD.date().isoformat(),
        pdh = div(p_hi), pdl = div(p_lo),
        asia_high = div(a_hi), asia_low = div(a_lo),
        london_high = div(l_hi), london_low = div(l_lo),
    )
    save_levels(outpath, lv)
    typer.echo(f"Wrote levels → {outpath}")
