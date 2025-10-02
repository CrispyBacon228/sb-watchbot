import argparse
from zoneinfo import ZoneInfo
import pandas as pd

NY = ZoneInfo("America/New_York")

# ---- knobs (kept permissive so you see alerts) ----
TICK = 0.25
KILL_START = (10, 0)     # 10:00 NY
KILL_END   = (11, 0)     # 11:00 NY
MIN_DISP_PTS = 0.25      # min body/disp; keep small
MIN_ZONE_PTS = 0.50      # min width; keep small
ENTRY_TOUCH_ONLY = True  # require touch of zone to enter
# ---------------------------------------------------

def _edt(ts_utc): return ts_utc.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S %Z")
def _w(a,b): return float(b)-float(a)

def find_fvgs_ict3(bars):
    """
    ICT 3-bar FVG:
      Bullish: low[i] > high[i-2]  => zone [high[i-2], low[i]]
      Bearish: high[i] < low[i-2]  => zone [high[i],   low[i-2]]  (stored as [lo,hi])
    """
    out = []
    for i in range(2, len(bars)):
        c0 = bars.iloc[i-2]
        c2 = bars.iloc[i]

        # bullish
        if c2["low"] > c0["high"]:
            lo, hi = float(c0["high"]), float(c2["low"])
            disp = c2["high"] - c2["low"]
            if disp >= MIN_DISP_PTS and _w(lo,hi) >= MIN_ZONE_PTS:
                out.append(dict(side="LONG", created_ts=c2["timestamp"], lo=lo, hi=hi, touched_ts=None))

        # bearish
        if c2["high"] < c0["low"]:
            lo, hi = float(c2["high"]), float(c0["low"])
            disp = c0["high"] - c0["low"]
            if disp >= MIN_DISP_PTS and _w(lo,hi) >= MIN_ZONE_PTS:
                out.append(dict(side="SHORT", created_ts=c2["timestamp"], lo=lo, hi=hi, touched_ts=None))
    return out

def scan_and_alert(df):
    fvgs = find_fvgs_ict3(df)

    # debug counts
    print(f"[DBG] bars={len(df)} fvgs={len(fvgs)}")

    alerts = []
    for _, row in df.iterrows():
        ts,o,h,l,c = row["timestamp"],row["open"],row["high"],row["low"],row["close"]
        for z in fvgs:
            if z["touched_ts"] is not None: continue
            if z["side"]=="LONG":
                if l <= z["hi"] and h >= z["lo"]:
                    z["touched_ts"] = ts
                    entry = z["hi"]; sl = z["lo"] - TICK; r = entry - sl
                    alerts.append(dict(side="LONG", when=ts, entry=entry, zone=(z["lo"],z["hi"]),
                                       sl=sl, r1=entry+r, r2=entry+2*r))
            else: # SHORT
                if h >= z["lo"] and l <= z["hi"]:
                    z["touched_ts"] = ts
                    entry = z["lo"]; sl = z["hi"] + TICK; r = sl - entry
                    alerts.append(dict(side="SHORT", when=ts, entry=entry, zone=(z["lo"],z["hi"]),
                                       sl=sl, r1=entry-r, r2=entry-2*r))
    print(f"[DBG] touches={sum(1 for z in fvgs if z['touched_ts'] is not None)} alerts={len(alerts)}")
    return alerts

def load_csv(path):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

    ny = df["timestamp"].dt.tz_convert(NY)
    sH,sM = KILL_START; eH,eM = KILL_END
    mask = (ny.dt.time >= pd.to_datetime(f"{sH:02d}:{sM:02d}").time()) & \
           (ny.dt.time <  pd.to_datetime(f"{eH:02d}:{eM:02d}").time())
    df = df.loc[mask, ["timestamp","open","high","low","close","volume"]].reset_index(drop=True)
    print(f"[DBG] killzone rows={len(df)}")
    return df

def print_alerts(alerts):
    for a in alerts:
        print(f"[ALERT] SB ENTRY {a['side']} | {_edt(a['when'])} | "
              f"Entry {a['entry']:.2f} | FVG[{a['zone'][0]:.2f},{a['zone'][1]:.2f}] | "
              f"SL {a['sl']:.2f} | 1R {a['r1']:.2f} | 2R {a['r2']:.2f}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--speed", type=float, default=0.0)  # kept for CLI compat
    args = ap.parse_args()

    df = load_csv(args.csv)
    if df.empty:
        print("No rows in killzone window."); return
    alerts = scan_and_alert(df)
    if not alerts:
        print("No alerts emitted. Try relaxing thresholds or add strategy debug prints."); return
    print_alerts(alerts)

if __name__ == "__main__":
    main()
