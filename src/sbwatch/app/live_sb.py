import os, time, json, argparse
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib import request

# -------- settings (mirror replay) --------
NY = ZoneInfo("America/New_York")
TICK = 0.25
STOP_BUF_TICKS = 6
KILL_START = (10, 0)
KILL_END   = (11, 0)
RTH_START  = (9, 30)
RTH_END    = (16, 0)

MIN_DISP_PTS = 1.25
MIN_ZONE_PTS = 1.00
FRESH_MAX_BARS = 6
ENTRY_MODE = "mean"
MIN_R_POINTS = 1.00
SWEEP_LOOKBACK = 120
SWEEP_WINDOW_BARS = 12
# ------------------------------------------

def send_discord(msg: str):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url: return
    try:
        data = json.dumps({"content": msg}).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        request.urlopen(req, timeout=5)
    except Exception:
        pass

def et(ts):
    return pd.to_datetime(ts, utc=True).tz_convert(NY).strftime("%Y-%m-%d %I:%M:%S %p %Z")

def _coerce(df):
    for c in ["open","high","low","close","volume"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna()

def load_rth(csv_path):
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    ts = df["timestamp"].dt.tz_convert(NY)
    mask = (ts.dt.time >= pd.to_datetime(f"{RTH_START[0]:02d}:{RTH_START[1]:02d}").time()) & \
           (ts.dt.time <  pd.to_datetime(f"{RTH_END[0]:02d}:{RTH_END[1]:02d}").time())
    return _coerce(df.loc[mask, ["timestamp","open","high","low","close","volume"]].copy())

def window_kz(df_full):
    ts = df_full["timestamp"].dt.tz_convert(NY)
    mask = (ts.dt.time >= pd.to_datetime(f"{KILL_START[0]:02d}:{KILL_START[1]:02d}").time()) & \
           (ts.dt.time <  pd.to_datetime(f"{KILL_END[0]:02d}:{KILL_END[1]:02d}").time())
    kz = df_full.loc[mask].copy()
    kz["i_full"] = kz.index
    return kz

# ---- sweep helpers (full-session) ----
def _swept_low_full(df, i):
    if i < 1: return False
    lo = max(0, i - SWEEP_LOOKBACK)
    prior_min = df.loc[lo:i-1, "low"].min()
    return float(df.loc[i, "low"]) < float(prior_min)

def _swept_high_full(df, i):
    if i < 1: return False
    lo = max(0, i - SWEEP_LOOKBACK)
    prior_max = df.loc[lo:i-1, "high"].max()
    return float(df.loc[i, "high"]) > float(prior_max)

def _had_recent_sweep_low(df, i):
    lo = max(0, i - SWEEP_WINDOW_BARS)
    return any(_swept_low_full(df, j) for j in range(lo, i+1))

def _had_recent_sweep_high(df, i):
    lo = max(0, i - SWEEP_WINDOW_BARS)
    return any(_swept_high_full(df, j) for j in range(lo, i+1))

def recent_sweep_low_extreme(df, i):
    lo = max(0, i - SWEEP_WINDOW_BARS)
    extreme = None
    for j in range(lo, i+1):
        if _swept_low_full(df, j):
            v = float(df.loc[j, "low"]); extreme = v if extreme is None else min(extreme, v)
    return extreme

def recent_sweep_high_extreme(df, i):
    lo = max(0, i - SWEEP_WINDOW_BARS)
    extreme = None
    for j in range(lo, i+1):
        if _swept_high_full(df, j):
            v = float(df.loc[j, "high"]); extreme = v if extreme is None else max(extreme, v)
    return extreme
# --------------------------------------

def entry_from_zone(side, zlo, zhi):
    return (zlo+zhi)/2.0 if ENTRY_MODE.lower()=="mean" else (zlo if side=="LONG" else zhi)

def stops_targets(side, entry, sweep_ext):
    buf = STOP_BUF_TICKS * TICK
    if side=="LONG":
        sl = sweep_ext - buf; r = entry - sl
        if r < MIN_R_POINTS: return None
        return sl, entry + r, entry + 2*r
    else:
        sl = sweep_ext + buf; r = sl - entry
        if r < MIN_R_POINTS: return None
        return sl, entry - r, entry - 2*r

def build_fvgs(df_full, df_kz):
    """3-bar FVGs formed on killzone bars; sweeps measured on full session."""
    out = []
    for i_kz in range(2, len(df_kz)):
        i0 = int(df_kz.loc[i_kz-2, "i_full"])
        i2 = int(df_kz.loc[i_kz,   "i_full"])
        c0, c2 = df_full.loc[i0], df_full.loc[i2]
        rng = float(c2["high"]) - float(c2["low"])
        if rng < MIN_DISP_PTS: continue

        # Bullish gap
        if float(c0["high"]) < float(c2["low"]):
            zlo, zhi = float(c0["high"]), float(c2["low"])
            if (zhi - zlo) >= MIN_ZONE_PTS and _had_recent_sweep_low(df_full, i2):
                se = recent_sweep_low_extreme(df_full, i2)
                if se is not None:
                    out.append(dict(side="LONG", zlo=zlo, zhi=zhi,
                                    created_idx_kz=i_kz, created_idx_full=i2,
                                    created_ts=df_full.loc[i2,"timestamp"],
                                    sweep_ext=se, touched=False))
            continue

        # Bearish gap
        if float(c2["high"]) < float(c0["low"]):
            zlo, zhi = float(c2["high"]), float(c0["low"])
            if (zhi - zlo) >= MIN_ZONE_PTS and _had_recent_sweep_high(df_full, i2):
                se = recent_sweep_high_extreme(df_full, i2)
                if se is not None:
                    out.append(dict(side="SHORT", zlo=zlo, zhi=zhi,
                                    created_idx_kz=i_kz, created_idx_full=i2,
                                    created_ts=df_full.loc[i2,"timestamp"],
                                    sweep_ext=se, touched=False))
    return out

def maybe_alert(df_kz, fvgs, sent_ids:set):
    """Check touches; print/Discord once per FVG."""
    alerts = 0
    for i_kz, row in df_kz.iterrows():
        h,l,c,ts = row["high"],row["low"],row["close"],row["timestamp"]
        for f in fvgs:
            if f["touched"]: continue
            # outside-in + confirm
            if f["side"]=="LONG":
                touched = (l <= f["zhi"]) and (h >= f["zlo"]) and (c > f["zlo"])
            else:
                touched = (h >= f["zlo"]) and (l <= f["zhi"]) and (c < f["zhi"])
            if not touched: continue
            if i_kz - f["created_idx_kz"] > FRESH_MAX_BARS: continue

            entry = entry_from_zone(f["side"], f["zlo"], f["zhi"])
            stk = stops_targets(f["side"], entry, f["sweep_ext"])
            if stk is None: continue
            sl, r1, r2 = stk

            f["touched"] = True
            key = (f["created_ts"], f["side"])
            if key in sent_ids: continue
            sent_ids.add(key)

            line = (f"[ALERT] SB ENTRY {f['side']:<5} | {et(ts)} | "
                    f"Entry {entry:.2f} | FVG({f['zlo']:.2f},{f['zhi']:.2f}) | "
                    f"SL {sl:.2f} | 1R {r1:.2f} | 2R {r2:.2f}")
            print(line); send_discord(line)
            alerts += 1
    return alerts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Live minute CSV that is continuously updated")
    ap.add_argument("--poll", type=float, default=5.0, help="seconds between polls")
    ap.add_argument("--heartbeat", action="store_true", help="send ready/armed messages")
    args = ap.parse_args()

    sent = set()
    last_sig = None
    if args.heartbeat:
        send_discord("🟢 SB Watchbot starting…")
    while True:
        try:
            df_full = load_rth(args.csv)
            if df_full.empty:
                time.sleep(args.poll); continue

            # Only operate during killzone; send a 10:00 ‘armed’ heartbeat
            now_et = datetime.now(timezone.utc).astimezone(NY)
            if (now_et.hour, now_et.minute) == KILL_START and last_sig != "armed":
                send_discord("⏱️ SB armed: 10:00–11:00 ET window live.")
                last_sig = "armed"
            if now_et.hour >= KILL_END[0] and now_et.minute >= KILL_END[1]:
                time.sleep(args.poll); continue

            df_kz = window_kz(df_full)
            if df_kz.empty:
                time.sleep(args.poll); continue

            # Build FVGs (stateful enough for one window)
            if "fvgs_cache" not in globals():
                globals()["fvgs_cache"] = build_fvgs(df_full, df_kz)
            else:
                # Rebuild each poll (cheap) so we don't miss new FVGs
                globals()["fvgs_cache"] = build_fvgs(df_full, df_kz)

            _ = maybe_alert(df_kz, globals()["fvgs_cache"], sent)
            time.sleep(args.poll)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("live loop error:", e)
            time.sleep(max(2.0, args.poll))
    send_discord("🟡 SB Watchbot stopped.")

if __name__ == "__main__":
    main()
