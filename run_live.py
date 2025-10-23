from __future__ import annotations

# --- keep src/ on sys.path (belt+suspenders when unit PYTHONPATH not present) ---
from pathlib import Path
import sys
BASE_DIR = Path(__file__).resolve().parent
SRC = BASE_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import os, json, datetime as dt
from zoneinfo import ZoneInfo
from sbwatch.live_adapter import iter_live_bars
from sbwatch.strategy import SBEngine

ET = ZoneInfo("America/New_York")

def _load_levels():
    p = BASE_DIR / "data" / "levels.json"
    if not p.exists():
        raise FileNotFoundError("data/levels.json not found. run --build-levels first.")
    payload = json.loads(p.read_text(encoding="utf-8"))
    levels = payload.get("levels") or {}
    date_str = payload.get("date")
    today = dt.datetime.now(tz=ET).date().isoformat()
    if date_str and date_str != today:
        print(f"[LIVE] WARNING: levels.json is {date_str}, today is {today}", file=sys.stderr)
    print("[LIVE] Loaded levels:", json.dumps(levels, sort_keys=True))
    return levels

def main():
    levels = _load_levels()
    eng = SBEngine(levels)
    for bar in iter_live_bars(run_seconds=None):
        eng.on_bar(bar.ts_epoch_ms, bar.open, bar.high, bar.low, bar.close)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
