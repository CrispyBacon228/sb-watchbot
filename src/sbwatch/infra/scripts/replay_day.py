#!/usr/bin/env python3
from __future__ import annotations
import os, sys, json, time
from datetime import datetime, date, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from db_client import get_historical

import pandas as pd
from pathlib import Path
def _load_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    try:
        load_dotenv(env_path)
    except Exception:
        # manual fallback
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k,v = line.split("=",1)
                import os; os.environ.setdefault(k.strip(), v.strip())
_load_env()


# ---------------- ENV ----------------
ENV = os.environ
API_KEY = ENV.get("DATABENTO_API_KEY", "")
SYMBOL  = ENV.get("SYMBOL", "NQ")
SCHEMA  = ENV.get("SCHEMA", "ohlcv-1m")
DIVISOR = float(ENV.get("DIVISOR", "1"))
TZ_ET   = ENV.get("TIMEZONE", "America/New_York")

# Replay controls (all optional)
REPLAY_ET_DATE = ENV.get("REPLAY_ET_DATE")   # "YYYY-MM-DD" of the day to replay (defaults to today ET)
REPLAY_SPEED   = ENV.get("REPLAY_SPEED", "fast")  # "fast" or "real"
REPLAY_SLEEP_S = float(ENV.get("REPLAY_SLEEP_S", "0.02"))  # pause per bar in fast mode
TEST_WEBHOOK   = ENV.get("DISCORD_WEBHOOK_URL_TEST", "")   # test channel
TICK_SIZE      = float(ENV.get("TICK_SIZE", "0.25"))        # for ±3 ticks near-level tagging
TOL            = TICK_SIZE * 3

if not API_KEY:
    print("ERROR: DATABENTO_API_KEY missing.", file=sys.stderr)
    sys.exit(2)

# ---------------- Optional: reuse your code if available ----------------
use_external_levels = False
use_external_alerts = False
use_external_strategy = False

# Try to use your capture_levels window + report logic
build_levels_for_day = None
try:
    import importlib.util, pathlib
    # prefer importing scripts.capture_levels if in path
    sys.path.insert(0, str(pathlib.Path(".").resolve()))
    from scripts.capture_levels import build_levels_for_day as _build_lv
    build_levels_for_day = _build_lv
    use_external_levels = True
except Exception as e:
    build_levels_for_day = None

# Try to use your alert formatter / gate if present
alert_gate = None
alert_builder = None
try:
    from sbwatch.alert_gate import should_alert as alert_gate  # hypothetical
    use_external_alerts = True
except Exception:
    alert_gate = None

try:
    from sbwatch.alerts import make_alert as alert_builder     # hypothetical
    use_external_strategy = True
except Exception:
    alert_builder = None

# ---------------- Helpers ----------------
def post_discord(url: str, content: str):
    if not url: return
    import http.client, json, urllib.parse
    u = urllib.parse.urlparse(url)
    body = json.dumps({"content": content})
    conn = http.client.HTTPSConnection(u.hostname, 443, timeout=10)
    try:
        conn.request("POST", u.path, body=body, headers={"Content-Type":"application/json"})
        conn.getresponse().read()
    finally:
        conn.close()

def _et_time(hhmm: str) -> dtime:
    h, m = map(int, hhmm.split(":"))
    return dtime(h, m)

def make_utc_range(day_et: date, start_hhmm: str, end_hhmm: str, tz: str = TZ_ET):
    z = ZoneInfo(tz)
    s_local = datetime.combine(day_et, _et_time(start_hhmm), tzinfo=z)
    e_local = datetime.combine(day_et, _et_time(end_hhmm), tzinfo=z)
    if end_hhmm <= start_hhmm:
        e_local += timedelta(days=1)
    return s_local.astimezone(timezone.utc), e_local.astimezone(timezone.utc)

def fetch_ohlcv(start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    from databento import Historical  # kept for type hints; creation uses helper
    cl = get_historical(API_KEY)
    df = cl.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=SYMBOL,
        schema=SCHEMA,
        start=start_utc,
        end=end_utc,
    ).to_df()
    for c in ("open","high","low","close"):
        if c in df.columns:
            df[c] = df[c] / DIVISOR
    if "ts" not in df.columns:
        df = df.reset_index().rename(columns={"ts_recv": "ts"})
    return df.sort_values("ts")

@dataclass
class Levels:
    asia_hi: float; asia_lo: float
    london_hi: float; london_lo: float
    prev_hi: float; prev_lo: float

def compute_levels(today_et: date) -> Levels:
    if use_external_levels and build_levels_for_day:
        # reuse your function, it should return a dict/obj with Asia/London/Prev H/L
        try:
            from databento import Historical  # kept for type hints; creation uses helper
            cl = get_historical(API_KEY)
            lv = build_levels_for_day(cl, today_et)  # using your code
            def g(d, hi): return float(d.get(hi)) if d and d.get(hi) is not None else float("nan")
            asia_hi = g(lv.get("Asia"), "high") if isinstance(lv, dict) else getattr(lv, "asia_hi", float("nan"))
            asia_lo = g(lv.get("Asia"), "low")  if isinstance(lv, dict) else getattr(lv, "asia_lo", float("nan"))
            london_hi = g(lv.get("London"), "high") if isinstance(lv, dict) else getattr(lv, "london_hi", float("nan"))
            london_lo = g(lv.get("London"), "low")  if isinstance(lv, dict) else getattr(lv, "london_lo", float("nan"))
            prev_hi = g(lv.get("Prev"), "high") if isinstance(lv, dict) else getattr(lv, "prev_hi", float("nan"))
            prev_lo = g(lv.get("Prev"), "low")  if isinstance(lv, dict) else getattr(lv, "prev_lo", float("nan"))
            return Levels(asia_hi, asia_lo, london_hi, london_lo, prev_hi, prev_lo)
        except Exception:
            pass  # fall through to local compute

    # Local compute windows that match your report defaults
    a_s, a_e = make_utc_range(today_et, "18:00", "00:00")
    l_s, l_e = make_utc_range(today_et, "02:00", "05:00")
    y = today_et - timedelta(days=1)
    p_s, p_e = make_utc_range(y, "09:30", "16:00")
    a = fetch_ohlcv(a_s, a_e); l = fetch_ohlcv(l_s, l_e); p = fetch_ohlcv(p_s, p_e)
    return Levels(
        float(a["high"].max()) if not a.empty else float("nan"),
        float(a["low"].min())  if not a.empty else float("nan"),
        float(l["high"].max()) if not l.empty else float("nan"),
        float(l["low"].min())  if not l.empty else float("nan"),
        float(p["high"].max()) if not p.empty else float("nan"),
        float(p["low"].min())  if not p.empty else float("nan"),
    )

# Minimal fallback detectors if your strategy modules aren t available
def fvg_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["bull_fvg"] = (out["low"].shift(-1) > out["high"].shift(1))
    out["bear_fvg"] = (out["high"].shift(-1) < out["low"].shift(1))
    return out.loc[out["bull_fvg"] | out["bear_fvg"], ["ts","open","high","low","close","bull_fvg","bear_fvg"]]

def sweep_signals(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    out = df.copy()
    prev_hi = out["high"].rolling(lookback).max().shift(1)
    prev_lo = out["low"].rolling(lookback).min().shift(1)
    cond_hi = (out["high"] > prev_hi) & (out["close"] < prev_hi)
    cond_lo = (out["low"]  < prev_lo)  & (out["close"] > prev_lo)
    sweeps = out.loc[cond_hi | cond_lo, ["ts","open","high","low","close"]].copy()
    sweeps["type"] = sweeps.apply(lambda r: "BUY_SIDE" if r["high"] >= out["high"].shift(1).rolling(lookback).max().loc[r.name] else "SELL_SIDE", axis=1)
    return sweeps

def near_level(px: float, lv: Levels) -> str | None:
    if abs(px - lv.asia_hi)   <= TOL: return "Asia High"
    if abs(px - lv.asia_lo)   <= TOL: return "Asia Low"
    if abs(px - lv.london_hi) <= TOL: return "London High"
    if abs(px - lv.london_lo) <= TOL: return "London Low"
    if abs(px - lv.prev_hi)   <= TOL: return "Prev Day High"
    if abs(px - lv.prev_lo)   <= TOL: return "Prev Day Low"
    return None

def format_sweep_msg(row: pd.Series, level_tag: str | None, tz: str) -> str:
    ts = pd.to_datetime(row["ts"]).tz_convert(ZoneInfo(tz)).strftime("%H:%M:%S")
    bias = "Short Bias" if row["type"] == "BUY_SIDE" else "Long Bias"
    price = row["high"] if row["type"]=="BUY_SIDE" else row["low"]
    lvl_line = f"Level: {level_tag} -> {bias}\\n" if level_tag else ""
    return (
        f"🕘 Sweep Detected\\n"
        f"{lvl_line}"
        f"Price: {price:.2f} (±3 ticks tolerance)\\n"
        f"When:  {ts} ET"
    )

def main():
    et_now = datetime.now(ZoneInfo(TZ_ET))
    today_et = date.fromisoformat(REPLAY_ET_DATE) if REPLAY_ET_DATE else et_now.date()

    # Full ET day replay window
    day_s_utc, day_e_utc = make_utc_range(today_et, "00:00", "00:00")

    print(f"[replay] {SYMBOL} {SCHEMA} {today_et} (ET)")
    df = fetch_ohlcv(day_s_utc, day_e_utc)
    if df.empty:
        print("No data returned.")
        return

    lv = compute_levels(today_et)

    log_path = f"data/replay-{today_et.isoformat()}.log"
    os.makedirs("data", exist_ok=True)
    out = open(log_path, "w")
    def log(line: str):
        print(line)
        out.write(line + "\\n"); out.flush()

    # Header like your Levels report
    log(f"SB Watchbot — Levels Report ({today_et})")
    log(f"Contract: {SYMBOL}")
    log(f"Asia   H/L: {lv.asia_hi:.2f} / {lv.asia_lo:.2f}  (18:00–00:00 ET)")
    log(f"London H/L: {lv.london_hi:.2f} / {lv.london_lo:.2f}  (02:00–05:00 ET)")
    log(f"Prev Day H/L: {lv.prev_hi:.2f} / {lv.prev_lo:.2f}  (09:30–16:00 ET, prev day)")
    log("")

    if TEST_WEBHOOK:
        post_discord(TEST_WEBHOOK, f"🧪 Replay {today_et} started. Logging to `{log_path}`.")

    # --- Use your strategy if present, otherwise fallback sweeps/FVG ---
    if use_external_strategy and alert_builder:
        # Try to feed each bar through your existing alert builder/gate.
        # We assume it exposes something like make_alert(bar)->str and alert_gate(alert)->bool.
        for _, r in df.iterrows():
            bar = {
                "ts": pd.to_datetime(r["ts"]),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r.get("volume", 0.0)),
            }
            try:
                alert = alert_builder(bar)
                if alert and (not alert_gate or alert_gate(alert)):
                    log(alert)
                    if TEST_WEBHOOK: post_discord(TEST_WEBHOOK, alert)
            except Exception:
                # If your API differs, fall back to local detectors for the remainder
                use_fallback = True
                break
            if REPLAY_SPEED == "real":
                time.sleep(60)   # 1m bars
            else:
                time.sleep(REPLAY_SLEEP_S)
    else:
        # Fallback detectors that mimic your alert text category
        sweeps = sweep_signals(df)
        fvgs   = fvg_signals(df)

        for _, r in sweeps.iterrows():
            lvl = near_level(r["high"] if r["type"]=="BUY_SIDE" else r["low"], lv)
            msg = format_sweep_msg(r, lvl, TZ_ET)
            log(msg + "\\n")
            if TEST_WEBHOOK: post_discord(TEST_WEBHOOK, msg)
            if REPLAY_SPEED == "real":
                time.sleep(60)
            else:
                time.sleep(REPLAY_SLEEP_S)

        for _, r in fvgs.iterrows():
            ts = pd.to_datetime(r["ts"]).tz_convert(ZoneInfo(TZ_ET)).strftime("%H:%M:%S")
            kind = "Bullish FVG" if bool(r.get("bull_fvg")) else "Bearish FVG"
            line = f"🧩 {kind} at {ts} ET  OHLC=({r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f})"
            log(line)
            if TEST_WEBHOOK: post_discord(TEST_WEBHOOK, line)
            if REPLAY_SPEED == "real":
                time.sleep(60)
            else:
                time.sleep(REPLAY_SLEEP_S)

    log("\\n[replay] Done.")
    out.close()
    if TEST_WEBHOOK:
        post_discord(TEST_WEBHOOK, f"🧪 Replay {today_et} finished. See `{log_path}`.")
if __name__ == "__main__":
    main()
