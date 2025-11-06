from __future__ import annotations

# === FAST CSV SOURCE START ===
from types import SimpleNamespace as _NS
import os
from sbwatch.stream.minute_proxy import iter_minute_csv_tail, iter_minute_csv_tail_fast

def get_bars():
    path = os.getenv("LIVE_MINUTE_PATH","data/live_minute.csv")
    return (iter_minute_csv_tail_fast(path)
            if os.getenv("FAST_UPDATES","1") == "1"
            else iter_minute_csv_tail(path))

def bars_compat():
    for _b in get_bars():
        # map Bar(o,h,l,c,v) -> bar.open/.high/.low/.close/.volume
        yield _NS(ts_ms=_b.ts_ms, open=_b.o, high=_b.h, low=_b.l, close=_b.c, volume=getattr(_b, 'v', 0.0))
# === FAST CSV SOURCE END ===





from sbwatch.stream.minute_proxy import iter_minute_csv_tail, iter_minute_csv_tail_fast
import os
print(f"[DEBUG] FAST_UPDATES={os.getenv('FAST_UPDATES')}")
#!/usr/bin/env python3

# keep src/ on sys.path so imports work under systemd
from pathlib import Path

# --- CSV bar source selector (FAST = intra-minute updates) ---
def get_bars():
    path = os.getenv('LIVE_MINUTE_PATH','data/live_minute.csv')
    if os.getenv('FAST_UPDATES','1') == '1':
        return iter_minute_csv_tail_fast(path)
    return iter_minute_csv_tail(path)

import sys
BASE_DIR = Path(__file__).resolve().parent
SRC = BASE_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json, datetime as dt
from zoneinfo import ZoneInfo

from sbwatch import notify
from sbwatch.live_adapter import iter_live_bars
from sbwatch.stream.minute_proxy import iter_minute_csv_tail
from sbwatch.strategy import SBEngine

ET = ZoneInfo("America/New_York")

def _load_levels() -> dict:
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

def main() -> None:
    levels = _load_levels()
    eng = SBEngine(levels)

    armed_sent = False
    for bar in bars_compat():
        print(f"[FAST] {bar.ts_ms} {bar.close}", flush=True)
        # normalize ts to ms
        ts_ms = getattr(bar, "ts_epoch_ms", None)
        if ts_ms is None:
            ts = getattr(bar, "ts_ms", None)
            ts_ms = int(ts) if ts is not None else int(getattr(bar, "ts", 0)) * 1000

        dt_et = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET)

        # 10:00 ET — ARMED (once)
        if not armed_sent and (dt_et.hour > 10 or (dt_et.hour == 10 and dt_et.minute >= 0)):
            notify.post_system_armed(when=ts_ms)
            armed_sent = True

        # 11:01 ET — if no entry happened, post NO SB and exit
        if dt_et.hour > 11 or (dt_et.hour == 11 and dt_et.minute >= 2):
            if not notify.has_entry_today(ts_ms):
                notify.post_no_sb(when=ts_ms)
            break

        # strategy tick
        eng.on_bar(ts_ms, bar.open, bar.high, bar.low, bar.close)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
# --- FAST selector fallback (added) ---
def _bars_source():
    path = os.getenv("LIVE_MINUTE_PATH","data/live_minute.csv")
    return (iter_minute_csv_tail_fast(path)
            if os.getenv("FAST_UPDATES","1")=="1"
            else iter_minute_csv_tail(path))
try:
    bars  # type: ignore
except NameError:
    bars = _bars_source()

# --- Map minute_proxy Bar(o,h,l,c,v) -> strategy-style bar(open,high,low,close,volume) ---
from types import SimpleNamespace as _NS
def bars_compat():
    for _b in get_bars():
        yield _NS(ts_ms=_b.ts_ms, open=_b.o, high=_b.h, low=_b.l, close=_b.c, volume=getattr(_b, 'v', 0.0))