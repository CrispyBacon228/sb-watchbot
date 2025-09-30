#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from datetime import datetime, timezone
import pandas as pd
from sbwatch.data.ohlcv import get_ohlcv_1m
from sbwatch.strategy.ict_sb import detect_signal_strict, simulate_trade, TradeResult

def main():
    p = argparse.ArgumentParser(description="SB Watchbot replay (ICT strict)")
    p.add_argument("--symbol", default="NQ")
    p.add_argument("--lookback", type=int, default=24*60, help="minutes of data to fetch")
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--max-mins", type=int, default=120)
    p.add_argument("--out", default="replay_trades.csv")
    args = p.parse_args()

    df = get_ohlcv_1m(args.symbol, lookback_mins=args.lookback)
    if df.empty:
        print("No data")
        sys.exit(1)
    if df["timestamp"].dtype.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

    now = datetime.now(timezone.utc)
    sig = detect_signal_strict(df, now)
    trades: list[TradeResult] = []

    if sig:
        idx_entry = len(df) - 1
        tr = simulate_trade(df, idx_entry, sig, rr=args.rr, max_minutes=args.max_mins)
        trades.append(tr)
        print(f"{tr.outcome} | {tr.side} entry={tr.entry:.2f} stop={tr.stop:.2f} tp={tr.tp:.2f} "
              f"entry_ts={tr.entry_ts} exit_ts={tr.exit_ts} exit={tr.exit_price:.2f}")
    else:
        print("No signal right now (strategy is strict 10–11 NY and close-based).")

    # Save CSV for inspection
    if trades:
        pd.DataFrame([t.__dict__ for t in trades]).to_csv(args.out, index=False)
        print("wrote", args.out)

if __name__ == "__main__":
    main()
