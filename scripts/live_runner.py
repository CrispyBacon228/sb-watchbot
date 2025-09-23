import os, sys, json
from datetime import datetime, timezone, timedelta

from sbwatch.app import load_levels_json, build_levels
from sbwatch.core.engine import SBEngine, SBParams

def today_str_tz(tz_name="America/New_York"):
    # keep simple: use UTC today (midnight) as our daily key unless you want tz support here
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def ensure_levels(date_str: str, verbose: bool=False):
    # Try to load; if not present or wrong date, build then reload
    try:
        lv = load_levels_json()
        if lv.date != date_str:
            if verbose: print(f"[levels] levels.json is for {lv.date}, rebuilding for {date_str}…")
            build_levels(date_str, verbose=verbose)
            lv = load_levels_json()
            if lv.date != date_str:
                raise RuntimeError(f"levels.json not for {date_str} after build")
        else:
            if verbose: print(f"[levels] Found levels for {date_str}")
        return lv
    except Exception as e:
        if verbose: print(f"[levels] load failed ({e}); building for {date_str}…")
        build_levels(date_str, verbose=verbose)
        lv = load_levels_json()
        if lv.date != date_str:
            raise RuntimeError(f"levels.json not for {date_str} after build")
        return lv

def main():
    verbose = os.getenv("VERBOSE", "0") == "1"
    date_str = os.getenv("DAY", "") or today_str_tz()

    # Sanity show env the strategy cares about
    print("=== ENV ===")
    for k in ("DATABENTO_API_KEY", "DB_DATASET", "DB_SCHEMA", "FRONT_SYMBOL"):
        print(f"{k}={os.getenv(k, '')}")
    print("===========\n")

    # Ensure levels for the selected day
    lv = ensure_levels(date_str, verbose=verbose)
    if verbose:
        print("levels.json:", json.dumps(lv.__dict__, indent=2))

    # Build your params (same defaults as smoke)
    params = SBParams(
        tz="America/New_York",
        kill_start="12:00", kill_end="13:30",
        sweep_ticks=4, disp_min_ticks=4, fvg_min_ticks=3,
        refill_tol_ticks=2, tp1_r=1.0, tp2_r=2.0,
        stop_buf_ticks=4, ref_lookback_minutes=60,
        require_fvg=False,
    )

    # Construct engine with levels
    eng = SBEngine(params, levels=lv)
    print("[live] Engine ready with levels for", lv.date)
    print("[live] At this point, attach your live feed adapter and drive `eng` with bars/ticks.")
    print("[live] (This runner proves your env + levels + strategy wiring are good.)")

if __name__ == "__main__":
    main()
