import argparse
import importlib
import os
import time
import pandas as pd

def load_strategy_hook():
    try:
        mod = importlib.import_module("sbwatch.strategy")
        return getattr(mod, "on_bar", None)
    except Exception:
        return None

def main(csv_path: str, speed: float = 0.0, verbose: bool = True):
    if not os.path.exists(csv_path):
        print(f"Replay file not found: {csv_path}")
        return

    # Ensure UTC-aware timestamps
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.sort_values("timestamp")

    on_bar = load_strategy_hook()
    if on_bar is None:
        print("No strategy hook (sbwatch.strategy.on_bar). Printing bars only.\n")
        for _, row in df.iterrows():
            print(f"{row['timestamp']}  O:{row.get('open')} H:{row.get('high')} "
                  f"L:{row.get('low')} C:{row.get('close')} V:{row.get('volume')}")
            if speed > 0: time.sleep(speed)
        return

    any_alert = False
    for _, row in df.iterrows():
        try:
            alerts = on_bar(row, verbose=verbose)
            if alerts:
                any_alert = True
                if isinstance(alerts, str):
                    alerts = [alerts]
                for msg in alerts:
                    print(f"[ALERT] {msg}")
        except Exception as e:
            print(f"[strategy error] {e}")

        if speed > 0:
            time.sleep(speed)

    if not any_alert and verbose:
        print("(No alerts emitted. Try --speed 0 and verbose on, or relax thresholds.)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV from replay_day (out/replay_YYYY-MM-DD.csv)")
    ap.add_argument("--speed", type=float, default=0.0, help="seconds to sleep between bars")
    ap.add_argument("--quiet", action="store_true", help="suppress debug prints from strategy")
    args = ap.parse_args()
    main(args.csv, args.speed, verbose=not args.quiet)
