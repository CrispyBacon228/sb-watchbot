from __future__ import annotations
import csv, json, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

# Make project imports work
ROOT = Path(__file__).resolve().parents[1]  # /opt/sb-simple
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sbwatch.strategy import SBEngine
from sbwatch import notify  # used only to mirror deeptrace messages if desired

ET = ZoneInfo("America/New_York")

def load_levels(levels_path: Path) -> dict:
    if not levels_path.exists():
        raise FileNotFoundError(f"levels file missing: {levels_path}")
    payload = json.loads(levels_path.read_text(encoding="utf-8"))
    return payload.get("levels") or {}

def run(csv_path: Path, levels_path: Path):
    levels = load_levels(levels_path)
    print(f"[TRACE] levels: {json.dumps(levels, sort_keys=True)}")
    eng = SBEngine(levels)

    entries = 0
    with csv_path.open() as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            ts_ms = int(r["ts_epoch_ms"])
            o = float(r["open"]); h = float(r["high"]); l = float(r["low"]); c = float(r["close"])
            before = getattr(eng, "entry_count", 0)
            eng.on_bar(ts_ms, o, h, l, c)
            after = getattr(eng, "entry_count", before)
            if after > before:
                entries += 1
                info = getattr(eng, "last_entry", {}) or {}
                side = info.get("side") or info.get("direction") or "entry"
                stop = info.get("stop"); tp1 = info.get("tp1"); tp2 = info.get("tp2")
                et = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET).strftime("%Y-%m-%d %H:%M:%S")
                print(f"[TRACE] ENTRY {side} {et} @ {c}  stop={stop} tp1={tp1} tp2={tp2}")
    print(f"[TRACE] Done. Entries detected: {entries}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to 1m CSV from pull_today_csv.py")
    ap.add_argument("--levels", default="/opt/sb-simple/data/levels.json")
    args = ap.parse_args()
    run(Path(args.csv), Path(args.levels))
