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

def parse_hm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)

def real_price(v) -> float:
    """
    Force any value >= 1000 to be interpreted as micro units (divide by 1000 or 10000).
    NQ usually comes as price * 100, or price * 1000, or price * 10000.
    We'll normalize so ~25,000 prints as ~25000.00.
    """
    x = float(v)
    while x > 100000:   # too big? scale it down until it's in normal range
        x /= 10
    return x

def main():
    sym  = (os.environ.get("SB_SYMBOL", "NQZ5") or "").upper()
    date = os.environ.get("CSV_DATE")
    start_str = os.environ.get("CSV_START", "09:30")
    end_str   = os.environ.get("CSV_END",   "12:00")

    if date:
        day = dt.datetime.strptime(date, "%Y-%m-%d").date()
    else:
        day = dt.datetime.now(tz=ET).date()

    sh, sm = parse_hm(start_str)
    eh, em = parse_hm(end_str)

    start_et = dt.datetime(day.year, day.month, day.day, sh, sm, tzinfo=ET)
    end_et   = dt.datetime(day.year, day.month, day.day, eh, em, tzinfo=ET)

    client = DBHistorical()
    data = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=[sym],
        stype_in="raw_symbol",
        schema="ohlcv-1m",
        start=start_et.astimezone(dt.timezone.utc).isoformat(),
        end=end_et  .astimezone(dt.timezone.utc).isoformat(),
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{day.isoformat()}_{sym}_1m.csv")

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_epoch_ms","open","high","low","close","volume"])
        for row in data:
            ts_ns = int(getattr(row, "ts_event", getattr(row, "ts_recv", 0)))
            ts_ms = ts_ns // 1_000_000
            w.writerow([
                ts_ms,
                real_price(row.open),
                real_price(row.high),
                real_price(row.low),
                real_price(row.close),
                getattr(row, "volume", "")
            ])

    print(out_path)

if __name__ == "__main__":
    main()
