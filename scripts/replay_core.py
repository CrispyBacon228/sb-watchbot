#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, date
from importlib import import_module

import pandas as pd

# Databento
try:
    from databento import Historical
except Exception as e:
    print("ERROR: databento package not available:", e, file=sys.stderr)
    sys.exit(1)

# Our package helpers
try:
    from sbw.timebox import make_utc_range, clamp_window, sort_by_ts, ET
    from sbw.alerts import dispatch as alert
except Exception as e:
    print("ERROR: sbw package imports failed:", e, file=sys.stderr)
    sys.exit(1)


DATASET = os.getenv("DB_DATASET", "GLBX.MDP3")
SCHEMA  = os.getenv("SCHEMA", "ohlcv-1m")
CONTRACT = os.getenv("CONTRACT", "NQZ5")          # override with your current
API_KEY = os.getenv("DATABENTO_API_KEY", "").strip()
REPLAY_ET_DATE = os.getenv("REPLAY_ET_DATE")      # YYYY-MM-DD
STRATEGY_PATH = os.getenv("STRATEGY_FN", "").strip()

if not API_KEY:
    print("ERROR: DATABENTO_API_KEY not set.", file=sys.stderr)
    sys.exit(1)


def _load_strategy(path: str):
    """Return a callable(row: pd.Series, **ctx) -> list[dict] | None, or None if not set."""
    if not path:
        return None
    try:
        mod, fn = path.rsplit(".", 1)
        return getattr(import_module(mod), fn)
    except Exception as e:
        alert({"type":"REPLAY_ERROR", "note": f"Failed to import STRATEGY_FN='{path}': {e}"})
        return None


def _fetch_bars(client: Historical, day_et: date, start_et="09:30", end_et="11:00") -> pd.DataFrame:
    s_utc, e_utc = make_utc_range(datetime.combine(day_et, datetime.min.time()), start_et, end_et)
    s_utc, e_utc = clamp_window(s_utc, e_utc, minutes=0)  # no buffer unless you want it
    try:
        df = client.timeseries.get_range(
            dataset=DATASET,
            symbols=CONTRACT,
            schema=SCHEMA,
            start=s_utc,
            end=e_utc,
        ).to_df()
        return sort_by_ts(df)
    except Exception as e:
        # Common causes: range after availability, symbol typo, wrong contract month
        alert({"type":"REPLAY_FETCH_ERROR", "note": f"{type(e).__name__}: {e}"})
        raise


def main():
    # Resolve ET date
    if REPLAY_ET_DATE:
        try:
            day_et = datetime.strptime(REPLAY_ET_DATE, "%Y-%m-%d").date()
        except ValueError:
            print("ERROR: REPLAY_ET_DATE must be YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        day_et = datetime.now(ET).date()

    # Start banner
    alert({"type": "REPLAY_START", "contract": CONTRACT, "date": str(day_et), "schema": SCHEMA})

    client = Historical(api_key=API_KEY)
    try:
        df = _fetch_bars(client, day_et, "09:30", "11:00")
    except Exception:
        # already alerted above
        return

    n_bars = int(0 if df is None else len(df))
    alert({"type":"REPLAY_DATA", "contract": CONTRACT, "date": str(day_et), "bars": n_bars})

    # Optional: load user strategy and emit alerts
    strat = _load_strategy(STRATEGY_PATH)
    sent = 0
    if strat and n_bars:
        ctx = {"contract": CONTRACT, "date_et": str(day_et)}
        # Iterate row-by-row; your strategy decides if something should alert
        for _, row in df.iterrows():
            try:
                events = strat(row, **ctx)
                if not events:
                    continue
                for evt in events:
                    alert(evt)
                    sent += 1
            except Exception as e:
                alert({"type":"REPLAY_STRATEGY_ERROR", "note": f"{type(e).__name__}: {e}"})

    alert({"type":"REPLAY_DONE", "contract": CONTRACT, "date": str(day_et), "alerts_sent": sent})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        alert({"type":"REPLAY_FATAL", "note": f"{type(e).__name__}: {e}"})
        raise
