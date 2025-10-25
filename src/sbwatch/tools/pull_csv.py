from __future__ import annotations
import os, sys, csv, datetime as dt
from zoneinfo import ZoneInfo

try:
    from databento import Historical as DBHistorical
except Exception as e:
    print("ERROR: databento client not installed:", e, file=sys.stderr)
    sys.exit(2)

ET = ZoneInfo("America/New_York")
OUT_DIR = "/opt/sb-simple/data/csv"

def et_range_for_today(start_h=9, start_m=30, end_h=12, end_m=0):
    today = dt.datetime.now(tz=ET).date()
    start = dt.datetime(today.year, today.month, today.day, start_h, start_m, tzinfo=ET)
    end   = dt.datetime(today.year, today.month, today.day, end_h,   end_m,   tzinfo=ET)
    return start, end

def main():
    sym = os.environ.get("SB_SYMBOL", "NQ")
    start_s = os.environ.get("CSV_START")
    end_s   = os.environ.get("CSV_END")

    if start_s and end_s:
        today = dt.datetime.now(tz=ET).date()
        sh, sm = map(int, start_s.split(":"))
        eh, em = map(int, end_s.split(":"))
        start = dt.datetime(today.year, today.month, today.day, sh, sm, tzinfo=ET)
        end   = dt.datetime(today.year, today.month, today.day, eh, em, tzinfo=ET)
    else:
        start, end = et_range_for_today(9,30,12,0)

    api_key = os.getenv("DATABENTO_API_KEY")
    if not api_key:
        print("ERROR: DATABENTO_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    client = DBHistorical(api_key=api_key)
    data = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=[sym],
        stype_in="continuous",
        schema="ohlcv-1m",
        start=start.astimezone(dt.timezone.utc).isoformat(),
        end=end.astimezone(dt.timezone.utc).isoformat(),
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{dt.datetime.now(tz=ET).date()}_{sym}_1m.csv")

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_epoch_ms","open","high","low","close","volume"])
        for row in data:
            ts_ms = int(getattr(row, "ts_event", getattr(row, "ts", 0))) // 1_000_000
            w.writerow([ts_ms, row.open, row.high, row.low, row.close, getattr(row, "volume", "")])

    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
