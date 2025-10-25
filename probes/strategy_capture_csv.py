from __future__ import annotations
import csv, json, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sbwatch.strategy import SBEngine
from sbwatch import notify as _notify

ET = ZoneInfo("America/New_York")

ENTRY_COUNT = 0
def _capture_post_entry(*args, **kwargs):
    # monkeypatch notify.post_entry so we SEE any entry attempts
    global ENTRY_COUNT
    ENTRY_COUNT += 1
    ts_ms = kwargs.get("when") or (args[0] if args else None)
    price = kwargs.get("price")
    side  = kwargs.get("side") or kwargs.get("direction") or "entry"
    et = dt.datetime.fromtimestamp((ts_ms or 0)/1000, tz=ET).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[CAPTURE] ENTRY {side} {et} @ {price} :: { {k:v for k,v in kwargs.items() if k not in ('webhook','session')} }")

_notify.post_entry = _capture_post_entry  # disable Discord, capture locally

def load_levels(p: Path) -> dict:
    payload = json.loads(p.read_text(encoding="utf-8"))
    return payload.get("levels") or {}

def run(csv_path: Path, levels_path: Path):
    levels = load_levels(levels_path)
    print(f"[CAPTURE] levels:", json.dumps(levels, sort_keys=True))
    eng = SBEngine(levels)

    # Try to bypass gating if present
    for attr in ("armed","is_armed","allow_trades"):
        if hasattr(eng, attr):
            setattr(eng, attr, True)

    bars = 0
    with csv_path.open() as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            ts_ms = int(r["ts_epoch_ms"])
            o = float(r["open"]); h = float(r["high"]); l = float(r["low"]); c = float(r["close"])
            eng.on_bar(ts_ms, o, h, l, c)
            bars += 1
    print(f"[CAPTURE] Done. Bars={bars}, Entries={ENTRY_COUNT}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--levels", default="/opt/sb-simple/data/levels.json")
    args = ap.parse_args()
    run(Path(args.csv), Path(args.levels))
