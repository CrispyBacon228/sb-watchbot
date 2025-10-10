import argparse, json, os
from zoneinfo import ZoneInfo
import pandas as pd
from urllib import request

NY = ZoneInfo("America/New_York")

# ======= Tunables (ICT SB 10–11) =======
TICK = 0.25
STOP_BUF_TICKS = 6
KILL_START = (10, 0)
KILL_END   = (11, 0)
RTH_START  = (9, 30)
RTH_END    = (16, 0)

MIN_DISP_PTS = 1.25
MIN_ZONE_PTS = 0.75
FRESH_MAX_BARS = 6
ENTRY_MODE = "mean"
MIN_R_POINTS = 1.00
SWEEP_LOOKBACK = 120
# ======================================
SWEEP_WINDOW_BARS = 12

def send_discord(text: str) -> None:
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        return
    try:
        data = json.dumps({"content": text}).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        request.urlopen(req, timeout=5)
    except Exception:
        pass

def et(ts):  # pretty NY string
    return pd.to_datetime(ts, utc=True).tz_convert(NY).strftime("%Y-%m-%d %I:%M:%S %p %Z")

def _coerce_nums(df):
    for c in ["open","high","low","close","volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna()

def load_csv_full_then_window(path: str, debug: bool=False):
    """Load full RTH session (9:30–16:00), then make a 10–11 window view.
       Add a 'i_full' column so we can map killzone bars to full-session indices.
    """
    df = _ensure_datetime(pd.read_csv(path, parse_dates=["timestamp"]))
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

    ts_ny = df["timestamp"].dt.tz_convert(NY)
    rs, re = RTH_START, RTH_END
    rth_mask = (ts_ny.dt.time >= pd.to_datetime(f"{rs[0]:02d}:{rs[1]:02d}").time()) & \
               (ts_ny.dt.time <  pd.to_datetime(f"{re[0]:02d}:{re[1]:02d}").time())
    df_full = _coerce_nums(df.loc[rth_mask, ["timestamp","open","high","low","close","volume"]].copy())
    df_full.reset_index(drop=True, inplace=True)

    ts_full_ny = df_full["timestamp"].dt.tz_convert(NY)
    ks, ke = KILL_START, KILL_END
    kz_mask = (ts_full_ny.dt.time >= pd.to_datetime(f"{ks[0]:02d}:{ks[1]:02d}").time()) & \
              (ts_full_ny.dt.time <  pd.to_datetime(f"{ke[0]:02d}:{ke[1]:02d}").time())

    # Build killzone view with mapping to full indices
    df_kz = df_full.loc[kz_mask].copy()
    df_kz["i_full"] = df_kz.index  # map each killzone row back to its full-session index
    df_kz.reset_index(drop=True, inplace=True)

    if debug:
        print(f"[DBG] killzone rows={len(df_kz)}")
        if not df_kz.empty:
            w_hi = df_kz["high"].max(); w_lo = df_kz["low"].min()
            print(f"[DBG] window 10–11ET hi/lo = {w_hi:.2f} / {w_lo:.2f}")
    return df_full, df_kz

def _swept_high_full(df_full: pd.DataFrame, idx_full: int) -> bool:
    """True if bar idx_full sweeps highs vs lookback."""
    if idx_full < 1: return False
    lo = max(0, idx_full - SWEEP_LOOKBACK)
    prior_max = df_full.loc[lo:idx_full-1, 'high'].max()
    return float(df_full.loc[idx_full, 'high']) > float(prior_max)

def _had_recent_sweep_high(df_full: pd.DataFrame, idx_full: int) -> bool:
    lo = max(0, idx_full - SWEEP_WINDOW_BARS)
    for j in range(lo, idx_full+1):
        if _swept_high_full(df_full, j):
            return True
    return False

def recent_sweep_high_extreme(df_full, idx_full):
    """Highest *high* among the bars in the recent sweep window that actually swept highs."""
    lo = max(0, idx_full - SWEEP_WINDOW_BARS)
    extreme = None
    for j in range(lo, idx_full + 1):
        if _swept_high_full(df_full, j):
            val = float(df_full.loc[j, "high"])
            extreme = val if extreme is None else max(extreme, val)
    return extreme

def _swept_low_full(df_full: pd.DataFrame, idx_full: int) -> bool:
    """True if bar idx_full sweeps lows vs lookback."""
    if idx_full < 1: return False
    lo = max(0, idx_full - SWEEP_LOOKBACK)
    prior_min = df_full.loc[lo:idx_full-1, 'low'].min()
    return float(df_full.loc[idx_full, 'low']) < float(prior_min)

def _had_recent_sweep_low(df_full: pd.DataFrame, idx_full: int) -> bool:
    lo = max(0, idx_full - SWEEP_WINDOW_BARS)
    for j in range(lo, idx_full+1):
        if _swept_low_full(df_full, j):
            return True
    return False

def recent_sweep_low_extreme(df_full, idx_full):
    """Lowest *low* among the bars in the recent sweep window that actually swept lows."""
    lo = max(0, idx_full - SWEEP_WINDOW_BARS)
    extreme = None
    for j in range(lo, idx_full + 1):
        if _swept_low_full(df_full, j):
            val = float(df_full.loc[j, "low"])
            extreme = val if extreme is None else min(extreme, val)
    return extreme

def find_fvgs_ict3(df_full, df_kz, debug: bool=False):
    """
    Build 3-bar FVGs on *killzone bars*, but evaluate sweeps using the full session.
    LONG: need recent sweep of lows; zone=(c0.high, c2.low); SL uses the *lowest* swept low ± buffer.
    SHORT: need recent sweep of highs; zone=(c2.high, c0.low); SL uses the *highest* swept high ± buffer.
    """
    out = []
    cnt_rng_ok = cnt_zone_ok = cnt_sweeps_hi = cnt_sweeps_lo = 0

    for i_kz in range(2, len(df_kz)):
        i0_full = int(df_kz.loc[i_kz - 2, "i_full"])
        i2_full = int(df_kz.loc[i_kz,     "i_full"])
        c0 = df_full.loc[i0_full]
        c2 = df_full.loc[i2_full]

        rng = float(c2["high"]) - float(c2["low"])
        if rng >= MIN_DISP_PTS:
            cnt_rng_ok += 1
        else:
            continue

        # Bullish gap: c0.high < c2.low
        if float(c0["high"]) < float(c2["low"]):
            zone_lo = float(c0["high"]); zone_hi = float(c2["low"])
            if (zone_hi - zone_lo) >= MIN_ZONE_PTS:
                cnt_zone_ok += 1
                if _had_recent_sweep_low(df_full, i2_full):
                    se = recent_sweep_low_extreme(df_full, i2_full)
                    if se is not None:
                        cnt_sweeps_lo += 1
                        out.append(dict(
                            side="LONG",
                            created_idx_kz=i_kz,
                            created_idx_full=i2_full,
                            created_ts=df_full.loc[i2_full, "timestamp"],
                            zlo=zone_lo, zhi=zone_hi,
                            swept_extreme=float(se),
                            touched_ts=None
                        ))
            continue

        # Bearish gap: c2.high < c0.low
        if float(c2["high"]) < float(c0["low"]):
            zone_lo = float(c2["high"]); zone_hi = float(c0["low"])
            if (zone_hi - zone_lo) >= MIN_ZONE_PTS:
                cnt_zone_ok += 1
                if _had_recent_sweep_high(df_full, i2_full):
                    se = recent_sweep_high_extreme(df_full, i2_full)
                    if se is not None:
                        cnt_sweeps_hi += 1
                        out.append(dict(
                            side="SHORT",
                            created_idx_kz=i_kz,
                            created_idx_full=i2_full,
                            created_ts=df_full.loc[i2_full, "timestamp"],
                            zlo=zone_lo, zhi=zone_hi,
                            swept_extreme=float(se),
                            touched_ts=None
                        ))
            continue

    if debug:
        print(f"[DBG] bars with range >= {MIN_DISP_PTS} pts: {cnt_rng_ok}")
        print(f"[DBG] zones >= {MIN_ZONE_PTS} pts: {cnt_zone_ok}")
        print(f"[DBG] recent-sweep lo/hi (<= {SWEEP_WINDOW_BARS} bars) in those bars: {cnt_sweeps_lo}/{cnt_sweeps_hi}")
        if out:
            print("[DBG] FVGs created:")
            for f in out:
                print(f"  - {et(f['created_ts'])} {f['side']:<5} zone=({f['zlo']:.2f},{f['zhi']:.2f}) sweep_extreme={f['swept_extreme']:.2f}")
        else:
            print("[DBG] No FVGs passed all gates.")
    return out

def _entry_from_zone(fvg):
    if ENTRY_MODE.lower() == "mean":
        return (fvg["zlo"] + fvg["zhi"]) / 2.0
    return fvg["zlo"] if fvg["side"] == "LONG" else fvg["zhi"]

def _stops_and_targets(side, entry, swept_extreme, debug: bool=False):
    buf = STOP_BUF_TICKS * TICK
    if side == "LONG":
        sl = swept_extreme - buf
        r  = entry - sl
        if r < MIN_R_POINTS:
            if debug: print(f"[DBG] skip LONG: R {r:.2f} < MIN_R {MIN_R_POINTS}")
            return None
        return sl, entry + r, entry + 2*r
    else:
        sl = swept_extreme + buf
        r  = sl - entry
        if r < MIN_R_POINTS:
            if debug: print(f"[DBG] skip SHORT: R {r:.2f} < MIN_R {MIN_R_POINTS}")
            return None
        return sl, entry - r, entry - 2*r

def scan_and_alert(df_full, df_kz, debug: bool=False):
    fvgs = find_fvgs_ict3(df_full, df_kz, debug=debug)
    print(f"[DBG] bars={len(df_kz)} fvgs={len(fvgs)}")

    alerts = []
    for i_kz, row in df_kz.iterrows():
        o, h, l, c, ts = row["open"], row["high"], row["low"], row["close"], row["timestamp"]

        for fvg in fvgs:
            if fvg["touched_ts"] is not None:
                continue

            # Touch logic: outside-in + confirm
            if fvg["side"] == "LONG":
                touched = (l <= fvg["zhi"]) and (h >= fvg["zlo"]) and (c > fvg["zlo"])
            else:
                touched = (h >= fvg["zlo"]) and (l <= fvg["zhi"]) and (c < fvg["zhi"])

            # Freshness (in killzone bars)
            if touched:
                bars_since = i_kz - fvg["created_idx_kz"]
                if bars_since > FRESH_MAX_BARS:
                    if debug: print(f"[DBG] touch too old ({bars_since} bars) at {et(ts)} for {fvg['side']}")
                    continue
                entry = _entry_from_zone(fvg)
                stk = _stops_and_targets(fvg["side"], entry, fvg["swept_extreme"], debug=debug)
                if stk is None:
                    continue
                sl, r1, r2 = stk
                fvg["touched_ts"] = ts
                alerts.append(dict(
                    side=fvg["side"],
                    when=et(ts),
                    entry=round(entry, 2),
                    zone=(round(fvg["zlo"],2), round(fvg["zhi"],2)),
                    sl=round(sl, 2),
                    r1=round(r1, 2),
                    r2=round(r2, 2)
                ))

    print(f"[DBG] touches={sum(1 for f in fvgs if f['touched_ts'] is not None)} alerts={len(alerts)}")
    return alerts

def print_alerts(alerts):
    for a in alerts:
        line = (f"[ALERT] SB ENTRY {a['side']:<5} | {a['when']} | "
                f"Entry {a['entry']:.2f} | FVG{a['zone']} | "
                f"SL {a['sl']:.2f} | 1R {a['r1']:.2f} | 2R {a['r2']:.2f}")
        print(line)
        try:
            send_discord(f"{a['when']} | {a['side']} ENTRY {a['entry']:.2f} | "
                         f"FVG{a['zone']} | SL {a['sl']:.2f} | "
                         f"1R {a['r1']:.2f} | 2R {a['r2']:.2f}")
        except Exception:
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--speed", type=float, default=0.0)  # not used
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    df_full, df_kz = load_csv_full_then_window(args.csv, debug=args.debug)
    if df_kz.empty:
        print("(No rows in killzone window)."); return
    alerts = scan_and_alert(df_full, df_kz, debug=args.debug)
    if not alerts:
        print("No alerts emitted. Try relaxing thresholds or verify data."); return
    print_alerts(alerts)

if __name__ == "__main__":
    main()

def _swept_low_full(df_full, idx_full) -> bool:
    """True if bar idx_full sweeps *lows* vs lookback (full session)."""
    if idx_full < 1:
        return False
    lo = max(0, idx_full - SWEEP_LOOKBACK)
    prior_min = df_full.loc[lo:idx_full-1, "low"].min()
    return float(df_full.loc[idx_full, "low"]) < float(prior_min)

def _swept_high_full(df_full, idx_full) -> bool:
    """True if bar idx_full sweeps *highs* vs lookback (full session)."""
    if idx_full < 1:
        return False
    lo = max(0, idx_full - SWEEP_LOOKBACK)
    prior_max = df_full.loc[lo:idx_full-1, "high"].max()
    return float(df_full.loc[idx_full, "high"]) > float(prior_max)

def _had_recent_sweep_low(df_full, idx_full) -> bool:
    """Any sweep of lows within the last SWEEP_WINDOW_BARS (inclusive)."""
    lo = max(0, idx_full - SWEEP_WINDOW_BARS)
    for j in range(lo, idx_full + 1):
        if _swept_low_full(df_full, j):
            return True
    return False

def _had_recent_sweep_high(df_full, idx_full) -> bool:
    """Any sweep of highs within the last SWEEP_WINDOW_BARS (inclusive)."""
    lo = max(0, idx_full - SWEEP_WINDOW_BARS)
    for j in range(lo, idx_full + 1):
        if _swept_high_full(df_full, j):
            return True
    return False

