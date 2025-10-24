from sbwatch import notify
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
    
# --- SB live session alert state ---
_ET = ZoneInfo("America/New_York")
_armed_sent = False
# we will rely on notify.has_entry_today() which reads the daily flag created by notify.post_entry()
for bar in iter_live_bars(run_seconds=None):
        # -- per-bar session alerts --
        # Extract timestamp in ms from your bar object; adjust field as needed:
        try:
            ts_ms = bar.ts_ms
        except AttributeError:
            try:
                ts_ms = bar.ts_epoch_ms
            except AttributeError:
                # LAST resort: assume bar.ts is seconds
                ts_ms = int(getattr(bar, "ts", 0)) * 1000

        import datetime as _dt
        dt_et = _dt.datetime.fromtimestamp(ts_ms/1000, tz=_ET)

        # 10:00 ET 'ARMED' (once)
        if not _armed_sent and (dt_et.hour>10 or (dt_et.hour==10 and dt_et.minute>=0)):
            notify.post_system_armed(when=ts_ms)
            _armed_sent = True

        # 11:01 ET 'NO SB' if no entry flag
        if dt_et.hour>11 or (dt_et.hour==11 and dt_et.minute>=1):
            if not notify.has_entry_today(ts_ms):
                notify.post_no_sb(when=ts_ms)
            break
        eng.on_bar(bar.ts_epoch_ms, bar.open, bar.high, bar.low, bar.close)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
