#!/usr/bin/env python3
import os, sys, json, time, datetime as dt
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from dotenv import load_dotenv
import pytz, requests

try:
    from databento import Historical, Live
except Exception:
    print("Databento SDK missing. pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# --- Config & constants ---
BASE_DIR = os.path.dirname(__file__)
ET = pytz.timezone("America/Indiana/Indianapolis")
UTC = pytz.utc
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_API_KEY = os.getenv("DB_API_KEY", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
DATASET = os.getenv("DATASET", "GLBX.MDP3")
SCHEMA  = os.getenv("SCHEMA",  "ohlcv-1m")
SYMBOL  = os.getenv("SYMBOL",  "NQZ5")
MIN_DISPLACEMENT_TICKS = int(os.getenv("MIN_DISPLACEMENT_TICKS", "8"))
MAX_LOOKBACK_MIN       = int(os.getenv("MAX_LOOKBACK_MIN", "200"))

INCLUDE_ASIA_LONDON = os.getenv("INCLUDE_ASIA_LONDON", "0") == "1"
ASIA_START  = os.getenv("ASIA_START",  "20:00")
ASIA_END    = os.getenv("ASIA_END",    "00:00")
LONDON_START= os.getenv("LONDON_START","02:00")
LONDON_END  = os.getenv("LONDON_END",  "05:00")

USE_PDH_PDL_AS_SWEEP = os.getenv("USE_PDH_PDL_AS_SWEEP", "1") == "1"
USE_ASIA_AS_SWEEP    = os.getenv("USE_ASIA_AS_SWEEP",    "1") == "1"
USE_LONDON_AS_SWEEP  = os.getenv("USE_LONDON_AS_SWEEP",  "1") == "1"

if not DB_API_KEY or not DISCORD_WEBHOOK:
    print("Missing DB_API_KEY or DISCORD_WEBHOOK in .env", file=sys.stderr)
    sys.exit(1)

TICK_SIZE = 0.25          # NQ tick
PRICE_DIVISOR = 1e9       # << correct divisor for GLBX.MDP3 OHLCV

@dataclass
class Candle:
    ts: dt.datetime
    o: float; h: float; l: float; c: float; v: int

def now_et() -> dt.datetime: return dt.datetime.now(tz=ET)
def to_utc_str(t: dt.datetime) -> str: return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def dsend(msg: str):
    try: requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=5)
    except Exception as e: print(f"Discord error: {e}", file=sys.stderr)

# --- helpers to read Databento rows/messages robustly ---
def _get_attr(obj, name, default=None):
    if hasattr(obj, name): return getattr(obj, name)
    try: return obj[name]
    except Exception: return default

def _parse_ts_ns(obj) -> Optional[int]:
    return _get_attr(obj, "ts", _get_attr(obj, "ts_event", None))

def record_to_candle(obj) -> Optional[Candle]:
    ts_ns = _parse_ts_ns(obj)
    if ts_ns is None: return None
    ts = dt.datetime.fromtimestamp(int(ts_ns) / 1e9, tz=UTC).astimezone(ET)
    o = _get_attr(obj, "open",  _get_attr(obj, "o", None))
    h = _get_attr(obj, "high",  _get_attr(obj, "h", None))
    l = _get_attr(obj, "low",   _get_attr(obj, "l", None))
    c = _get_attr(obj, "close", _get_attr(obj, "c", None))
    v = _get_attr(obj, "volume", _get_attr(obj, "v", 0)) or 0
    if None in (o, h, l, c): return None
    return Candle(ts, float(o)/PRICE_DIVISOR, float(h)/PRICE_DIVISOR,
                  float(l)/PRICE_DIVISOR, float(c)/PRICE_DIVISOR, int(v))

# --- Historical fetch ---
def fetch_ohlcv_1m(start_et: dt.datetime, end_et: dt.datetime) -> List[Candle]:
    client = Historical(DB_API_KEY)
    table = client.timeseries.get_range(
        dataset=DATASET, symbols=[SYMBOL], schema=SCHEMA,
        start=to_utc_str(start_et), end=to_utc_str(end_et)
    )
    out: List[Candle] = []
    for row in table:
        c = record_to_candle(row)
        if c: out.append(c)
    return out

def bounds_et(day: dt.date, hhmm_start: str, hhmm_end: str, allow_prevday_start=False) -> Tuple[dt.datetime, dt.datetime]:
    h1,m1 = map(int, hhmm_start.split(":"))
    h2,m2 = map(int, hhmm_end.split(":"))
    start = ET.localize(dt.datetime.combine(day, dt.time(h1,m1)))
    end   = ET.localize(dt.datetime.combine(day, dt.time(h2,m2)))
    # If session crosses midnight (e.g., 20:00 -> 00:00), treat start as previous day
    if allow_prevday_start and (h1 > h2 or hhmm_end == "00:00"):
        start = start - dt.timedelta(days=1)
    return start, end if end > start else end + dt.timedelta(days=1)

def regular_session_bounds_et(day: dt.date):
    return bounds_et(day, "09:30", "16:00")

def level_from_window(start_et: dt.datetime, end_et: dt.datetime) -> Tuple[float, float]:
    cs = fetch_ohlcv_1m(start_et, end_et)
    if not cs: raise RuntimeError(f"No data for window {start_et}–{end_et}")
    return max(c.h for c in cs), min(c.l for c in cs)

def build_levels_for_today() -> Dict[str, float]:
    today = now_et().date()

    # 1) 09:00–09:59 box (pre-10am)
    box_s, box_e = bounds_et(today, "09:00", "09:59")
    box_high, box_low = level_from_window(box_s, box_e)

    # 2) PDH/PDL from prior regular session (09:30–16:00 previous weekday)
    prior = today - dt.timedelta(days=1)
    while prior.weekday() >= 5: prior -= dt.timedelta(days=1)
    rs_s, rs_e = regular_session_bounds_et(prior)
    try:
        pdh, pdl = level_from_window(rs_s, rs_e)
    except Exception:
        pdh, pdl = box_high, box_low  # fallback

    levels = {
        "box_high": box_high, "box_low": box_low,
        "pdh": pdh, "pdl": pdl
    }

    # 3) Optional Asia/London levels
    if INCLUDE_ASIA_LONDON:
        asia_s, asia_e = bounds_et(today, ASIA_START, ASIA_END, allow_prevday_start=True)
        london_s, london_e = bounds_et(today, LONDON_START, LONDON_END)
        try:
            asia_high, asia_low = level_from_window(asia_s, asia_e)
            levels["asia_high"] = asia_high; levels["asia_low"] = asia_low
        except Exception:
            pass
        try:
            lon_high, lon_low = level_from_window(london_s, london_e)
            levels["london_high"] = lon_high; levels["london_low"] = lon_low
        except Exception:
            pass

    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    with open(os.path.join(BASE_DIR, "data", "levels.json"), "w") as f:
        json.dump({"date": str(today), "levels": levels}, f, indent=2)
    return levels

def displacement_ok(a: float, b: float) -> bool:
    return abs(a - b) >= MIN_DISPLACEMENT_TICKS * TICK_SIZE

def detect_fvg_3bar(c1: Candle, c2: Candle, c3: Candle):
    # Bull: c3.low > c1.high  | Bear: c3.high < c1.low
    if c3.l > c1.h and displacement_ok(c3.c, c1.c):
        return ("bull", (c1.h + c3.l) / 2.0)
    if c3.h < c1.l and displacement_ok(c1.c, c3.c):
        return ("bear", (c3.h + c1.l) / 2.0)
    return (None, None)

def _swept_any(c: Candle, levels: Dict[str, float], direction: str) -> bool:
    candidates = []
    # 9:00 box is always included
    if direction == "bull": candidates += [levels["box_low"]]
    if direction == "bear": candidates += [levels["box_high"]]
    # optional PDH/PDL
    if USE_PDH_PDL_AS_SWEEP:
        if direction == "bull": candidates += [levels.get("pdl")]
        if direction == "bear": candidates += [levels.get("pdh")]
    # optional Asia/London
    if USE_ASIA_AS_SWEEP:
        if direction == "bull": candidates += [levels.get("asia_low")]
        if direction == "bear": candidates += [levels.get("asia_high")]
    if USE_LONDON_AS_SWEEP:
        if direction == "bull": candidates += [levels.get("london_low")]
        if direction == "bear": candidates += [levels.get("london_high")]

    candidates = [x for x in candidates if x is not None]
    if not candidates: return False

    if direction == "bull":
        # wick below any candidate and close back above it
        return any((c.l < L and c.c > L) for L in candidates)
    else:
        # wick above any candidate and close back below it
        return any((c.h > L and c.c < L) for L in candidates)


def live_run():
    import json, os, datetime as dt
    # Ensure logs dir
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    log_path = os.path.join(BASE_DIR, "logs", "live.log")
    log = open(log_path, "a", buffering=1)  # line-buffered

    # Load levels
    with open(os.path.join(BASE_DIR, "data", "levels.json")) as f:
        levels = json.load(f)["levels"]

    # Log the loaded levels for visibility
    def _fmt(x): 
        try: return f"{float(x):.2f}"
        except: return str(x)
    log.write("[CHECK] Loaded levels -> "
              f"box_high={_fmt(levels.get('box_high'))} "
              f"box_low={_fmt(levels.get('box_low'))} "
              f"pdh={_fmt(levels.get('pdh'))} "
              f"pdl={_fmt(levels.get('pdl'))} "
              f"asia_high={_fmt(levels.get('asia_high'))} "
              f"asia_low={_fmt(levels.get('asia_low'))} "
              f"london_high={_fmt(levels.get('london_high'))} "
              f"london_low={_fmt(levels.get('london_low'))}\n")

    # Time window (supports LIVE_START/LIVE_END overrides for testing)
    today = now_et().date()
    _ls = os.getenv("LIVE_START", "10:00")
    _le = os.getenv("LIVE_END",   "11:00")
    _h1,_m1 = map(int, _ls.split(":"))
    _h2,_m2 = map(int, _le.split(":"))
    start_et = ET.localize(dt.datetime.combine(today, dt.time(_h1,_m1)))
    end_et   = ET.localize(dt.datetime.combine(today, dt.time(_h2,_m2)))
    log.write(f"[CHECK] Starting live from {_ls} to {_le} (ET) ...\n")

    now = now_et()
    if now < start_et:
        dsend(f"🟡 SB Live waiting for {_ls}–{_le} ET…")
        while now_et() < start_et:
            time.sleep(1)
    elif now >= end_et:
        dsend("⏹️ SB Live skipped: window ended.")
        log.write("[CHECK] Window already ended — skipping.\n")
        log.close()
        return

    client = Live(DB_API_KEY)
    client.subscribe(dataset=DATASET, schema=SCHEMA, symbols=[SYMBOL])
    dsend(f"🟢 SB Live started for {SYMBOL} | Window: {_ls}–{_le} ET")

    buf: List[Candle] = []
    fired_bull = False
    fired_bear = False

    for msg in client:
        c = record_to_candle(msg)  # divisor applied here
        if not c:
            continue

        # Log every single bar
        log.write(f"[BAR] {c.ts.strftime('%H:%M:%S')} "
                  f"O:{c.o:.2f} H:{c.h:.2f} L:{c.l:.2f} C:{c.c:.2f}\n")

        if c.ts < start_et:
            continue
        if c.ts >= end_et:
            dsend("⏹️ SB Live ending: window complete.")
            log.write("[CHECK] Live run finished.\n")
            break

        buf.append(c)
        if len(buf) < 3:
            continue

        c1, c2, c3 = buf[-3], buf[-2], buf[-1]
        bull_sweep = _swept_any(c3, levels, "bull")
        bear_sweep = _swept_any(c3, levels, "bear")

        kind, entry = detect_fvg_3bar(c1, c2, c3)

        if kind == "bull" and bull_sweep and not fired_bull:
            sl = min(c1.l, c2.l, c3.l) - TICK_SIZE
            rr = entry - sl
            dsend(
                f"🟢 **SB Long** {SYMBOL}\n"
                f"Entry (FVG MT): {entry:.2f} | SL: {sl:.2f}\n"
                f"TP1 (1R): {entry+rr:.2f} | TP2 (2R): {entry+2*rr:.2f}\n"
                f"Swept: BOX/Asia/London/PDL (as enabled)\n"
                f"Bar: {c3.ts.strftime('%H:%M')} ET"
            )
            log.write(f"[ALERT] LONG entry={entry:.2f} sl={sl:.2f} tp1={(entry+rr):.2f} tp2={(entry+2*rr):.2f}\n")
            fired_bull = True

        if kind == "bear" and bear_sweep and not fired_bear:
            sl = max(c1.h, c2.h, c3.h) + TICK_SIZE
            rr = sl - entry
            dsend(
                f"🔴 **SB Short** {SYMBOL}\n"
                f"Entry (FVG MT): {entry:.2f} | SL: {sl:.2f}\n"
                f"TP1 (1R): {entry-rr:.2f} | TP2 (2R): {entry-2*rr:.2f}\n"
                f"Swept: BOX/Asia/London/PDH (as enabled)\n"
                f"Bar: {c3.ts.strftime('%H:%M')} ET"
            )
            log.write(f"[ALERT] SHORT entry={entry:.2f} sl={sl:.2f} tp1={(entry-rr):.2f} tp2={(entry-2*rr):.2f}\n")
            fired_bear = True

        if len(buf) > MAX_LOOKBACK_MIN:
            buf = buf[-MAX_LOOKBACK_MIN:]
    log.close()


def levels_cmd():
    levels = build_levels_for_today()
    lines = [
        f"Box 09:00–09:59 → High: {levels['box_high']:.2f}  Low: {levels['box_low']:.2f}",
        f"PDH: {levels['pdh']:.2f}  PDL: {levels['pdl']:.2f}",
    ]
    if "asia_high" in levels and "asia_low" in levels:
        lines.append(f"Asia H/L: {levels['asia_high']:.2f} / {levels['asia_low']:.2f}")
    if "london_high" in levels and "london_low" in levels:
        lines.append(f"London H/L: {levels['london_high']:.2f} / {levels['london_low']:.2f}")
    dsend("📐 SB Levels built:\n" + "\n".join(lines))
    print(json.dumps({"ok": True, "levels": levels}, indent=2))

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--build-levels":
        levels_cmd()
    elif arg == "--live":
        live_run()
    else:
        print("Usage: sb_bot.py --build-levels | --live")
        sys.exit(2)
