from __future__ import annotations
import csv, json, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

def in_window(ts_ms: int, start: dt.datetime, end: dt.datetime) -> bool:
    """True if ts is in [start, end). If end <= start, treat as next-day wrap."""
    t = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET)
    if end <= start:
        end = end + dt.timedelta(days=1)
        if t < start:
            t += dt.timedelta(days=1)
    return start <= t < end

def hl_from_csv(csv_path: Path, pred) -> tuple[float|None, float|None]:
    hi, lo = None, None
    with csv_path.open() as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            ts = int(r["ts_epoch_ms"])
            if pred(ts):
                h = float(r["high"]); l = float(r["low"])
                hi = h if hi is None or h > hi else hi
                lo = l if lo is None or l < lo else lo
    return hi, lo

def build_levels(target_date: dt.date, day_csv: Path, prev_rth_csv: Path) -> dict:
    d = target_date

    # Session bounds (ET)
    asia_start   = dt.datetime(d.year, d.month, d.day, 20, 0, tzinfo=ET)   # 20:00
    asia_end     = dt.datetime(d.year, d.month, d.day,  0, 0, tzinfo=ET)   # 24:00 ≡ next-day 00:00 (wrap)
    london_start = dt.datetime(d.year, d.month, d.day,  2, 0, tzinfo=ET)   # 02:00
    london_end   = dt.datetime(d.year, d.month, d.day,  5, 0, tzinfo=ET)   # 05:00

    asia_hi, asia_lo = hl_from_csv(day_csv, lambda ts: in_window(ts, asia_start, asia_end))
    lon_hi,  lon_lo  = hl_from_csv(day_csv, lambda ts: in_window(ts, london_start, london_end))

    # Prior RTH (previous calendar day 09:30–16:00 ET). If you want last trading day, set PREV manually upstream.
    prev = d - dt.timedelta(days=1)
    rth_start = dt.datetime(prev.year, prev.month, prev.day, 9, 30, tzinfo=ET)
    rth_end   = dt.datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=ET)
    pdh, pdl  = hl_from_csv(prev_rth_csv, lambda ts: in_window(ts, rth_start, rth_end))

    return {
        "asia_high": asia_hi, "asia_low": asia_lo,
        "london_high": lon_hi, "london_low": lon_lo,
        "pdh": pdh, "pdl": pdl,
        "am_high": None, "am_low": None,
    }

def main():
    if len(sys.argv) != 4:
        print("usage: python -m sbwatch.tools.levels_from_csv YYYY-MM-DD DAY_CSV PREV_RTH_CSV", file=sys.stderr)
        sys.exit(2)
    date_s, day_csv_s, prev_csv_s = sys.argv[1:]
    d = dt.date.fromisoformat(date_s)
    lvls = build_levels(d, Path(day_csv_s), Path(prev_csv_s))
    out = {"date": d.isoformat(), "levels": lvls}
    out_path = Path("/opt/sb-simple/data/levels.json")
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(str(out_path))

if __name__ == "__main__":
    main()
