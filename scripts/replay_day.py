#!/usr/bin/env python3
from __future__ import annotations
import argparse
from datetime import datetime, date, timedelta, timezone
import pytz
import pandas as pd

from sbwatch.data.range import get_ohlcv_range_1m
from sbwatch.strategy.ict_sb import detect_signal_strict, simulate_trade

NY = pytz.timezone("America/New_York")

def ny_to_utc(d: date, h: int, m: int = 0) -> datetime:
    return NY.localize(datetime(d.year, d.month, d.day, h, m, 0)).astimezone(timezone.utc)

def main():
    ap = argparse.ArgumentParser(description="Replay a specific day and show alerts during 10–11 NY.")
    ap.add_argument("--symbol", default="NQ")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (NY session day)")
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--max-mins", type=int, default=120)
    ap.add_argument("--csv", default="replay_day_trades.csv")
    ap.add_argument("--debug", action="store_true", help="Explain per-bar why no alert")
    ap.add_argument("--loose", action="store_true", help="Looser rules: disp>=0.3, FVG optional, touch entry OK")
    args = ap.parse_args()

    d = date.fromisoformat(args.date)
    day_start = ny_to_utc(d, 0, 0)
    day_end   = ny_to_utc(d+timedelta(days=1), 0, 0)

    df = get_ohlcv_range_1m(args.symbol, day_start, day_end)
    if df.empty:
        print("[replay] No data for that day.")
        return
    if df["timestamp"].dtype.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

    start_ny = ny_to_utc(d, 10, 0)
    end_ny   = ny_to_utc(d, 11, 0)

    disp_min = 0.30 if args.loose else 0.60
    require_fvg = False if args.loose else True
    entry_mode = "touch" if args.loose else "fvg_return"

    trades = []
    alerts = []
    checks = []

    # Iterate minute-by-minute in the 10–11 window
    for i in range(len(df)):
        now = df.iloc[i]["timestamp"]
        if not (start_ny <= now < end_ny):
            continue

        sig = None
        if args.debug:
            sig, ex = detect_signal_strict(
                df.iloc[:i+1].copy(), now,
                disp_min=disp_min, require_fvg=require_fvg, entry_mode=entry_mode, explain=True
            )
            checks.append({
                "timestamp": now, "reason": ex.reason if sig is None else "ALERT",
                "disp": ex.disp_value, "fvg_ok": ex.fvg_ok, "price_in_fvg": ex.price_in_fvg,
                "asia_high": ex.asia_high, "asia_low": ex.asia_low,
            })
        else:
            sig = detect_signal_strict(
                df.iloc[:i+1].copy(), now,
                disp_min=disp_min, require_fvg=require_fvg, entry_mode=entry_mode
            )

        if sig:
            msg = f"{now.isoformat()} — ALERT {sig.side} @ {sig.price:.2f} (AsiaH={sig.asia_high:.2f}, AsiaL={sig.asia_low:.2f})"
            alerts.append(msg)
            tr = simulate_trade(df, i, sig, rr=args.rr, max_minutes=args.max_mins)
            trades.append(tr)
            print(msg)
            print(f"  → {tr.outcome} | entry={tr.entry:.2f} stop={tr.stop:.2f} tp={tr.tp:.2f} exit={tr.exit_price:.2f} at {tr.exit_ts}")

    # ---- Always print a summary ----
    print(f"[replay] Date={args.date} Symbol={args.symbol} Window=10:00–11:00 NY "
          f"Mode={'LOOSE' if args.loose else 'STRICT'} disp_min={disp_min} require_fvg={require_fvg} entry={entry_mode}")
    print(f"[replay] Alerts found: {len(alerts)}  Trades simulated: {len(trades)}")

    if trades:
        out = args.csv
        pd.DataFrame([t.__dict__ for t in trades]).to_csv(out, index=False)
        print(f"[replay] Wrote {out}")
        try:
            # Pretty print to terminal
            print(pd.DataFrame([t.__dict__ for t in trades]).to_string(index=False))
        except Exception:
            pass

    if args.debug:
        dbg = "replay_day_debug.csv"
        pd.DataFrame(checks).to_csv(dbg, index=False)
        print(f"[replay] Wrote {dbg} (per-minute reasons).")

if __name__ == "__main__":
    main()
