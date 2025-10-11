import argparse, os, sys, subprocess, tempfile
import datetime as dt
from zoneinfo import ZoneInfo
from sbwatch.data.db_fetch import fetch_range


from datetime import datetime, date
try:
    from zoneinfo import ZoneInfo
except Exception:
    from backports.zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
def _is_weekend(d: date) -> bool: return d.weekday() >= 5

ET = ZoneInfo("America/New_York")

def et_window_to_utc(the_date: dt.date, start_et="09:30", end_et="11:05"):
    sh, sm = map(int, start_et.split(":"))
    eh, em = map(int, end_et.split(":"))
    start_et_dt = dt.datetime(the_date.year, the_date.month, the_date.day, sh, sm, tzinfo=ET)
    end_et_dt   = dt.datetime(the_date.year, the_date.month, the_date.day, eh, em, tzinfo=ET)
    # include full 11:05 bar
    end_et_dt = end_et_dt + dt.timedelta(minutes=1)
    return start_et_dt.astimezone(dt.timezone.utc), end_et_dt.astimezone(dt.timezone.utc)

def main():
    import pandas as pd

    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--start-et", default="09:30")
    p.add_argument("--end-et",   default="11:05")
    args = p.parse_args()

    y, m, d = map(int, args.date.split("-"))
    start_utc, end_utc = et_window_to_utc(dt.date(y, m, d), args.start_et, args.end_et)
    print(f"Using DATE={args.date} ET, window {args.start_et}–{args.end_et} ET")
    print(f"UTC range: {start_utc.isoformat()} → {end_utc.isoformat()}")

    # 1) Fetch bars
    data = fetch_range(start_utc, end_utc)

    # 2) DBNStore → DataFrame if needed
    df = data.to_df() if hasattr(data, "to_df") else data

    # ---- Normalize timestamp ----
    # Case A: timestamp already a column (best effort common names)
    time_col = next((c for c in ["timestamp","ts_event","ts","time","datetime","ts_recv"] if c in df.columns), None)

    # Case B: time is on the index (very common with Databento OHLCV)
    if time_col is None:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={"index": "ts_event"})
            time_col = "ts_event"
        elif df.index.name in ("ts_event","ts_recv","time","datetime"):
            name = df.index.name
            df = df.reset_index()
            time_col = name

    if time_col is None:
        print("❌ No timestamp-like column or index found. Columns:", list(df.columns), " Index name:", df.index.name)
        sys.exit(1)

    # Convert to UTC datetimes, make the exact 'timestamp' column the replay expects
    s = df[time_col]
    if pd.api.types.is_integer_dtype(s) or pd.api.types.is_float_dtype(s):
        # Databento nano/epoch → assume ns
        ts = pd.to_datetime(s, unit="ns", utc=True)
    else:
        ts = pd.to_datetime(s, utc=True, errors="coerce")

    if ts.isna().any():
        print("❌ Failed to convert timestamps from", time_col)
        print(df[[time_col]].head())
        sys.exit(1)

    df = df.copy()
    # ISO8601 UTC with +0000 so pandas parse_dates=['timestamp'] works on the other side
    df["timestamp"] = ts.dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    # 3) Select columns for the replay CSV
    out_cols = [c for c in ["timestamp","open","high","low","close","volume"] if c in df.columns]
    if "timestamp" not in out_cols:
        out_cols = ["timestamp"] + [c for c in ["open","high","low","close","volume"] if c in df.columns]

    # 4) Write temp CSV
    with tempfile.NamedTemporaryFile(prefix=f"replay_{args.date}_", suffix=".csv", delete=False) as tmp:
        temp_csv = tmp.name
    df.to_csv(temp_csv, index=False, columns=out_cols)
    print(f"✅ Wrote temp CSV for replay: {temp_csv}")
    # print a tiny preview for sanity
    try:
        print(df[out_cols].head(3).to_string(index=False))
    except Exception:
        pass

    # 5) Run your existing replay CLI (expects --csv only)
    cmd = [sys.executable, "-m", "sbwatch.app.replay_alerts", "--csv", temp_csv]
    subprocess.check_call(cmd)
    print("✅ Replay completed successfully.")

if __name__ == "__main__":
    main()