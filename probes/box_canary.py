#!/usr/bin/env python3
import os, sys, json, csv
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from src.sbwatch.notify import post_discord

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]

def load_levels():
    p = ROOT / "data" / "levels.json"
    with open(p, "r") as f:
        return json.load(f)

def iter_csv(path: Path):
    def parse_ts(s):
        s = str(s).strip()
        if s.isdigit() and len(s) >= 12: return int(s)             # unix ms
        if s.isdigit():                      return int(s) * 1000   # unix sec
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return int(dt.timestamp() * 1000)
    with open(path, "r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            yield (
                parse_ts(row["ts"]),
                float(row["open"]), float(row["high"]),
                float(row["low"]),  float(row["close"])
            )

def iter_stdin():
    for line in sys.stdin:
        line=line.strip()
        if not line: continue
        o=json.loads(line)
        ts=o["ts"]
        if isinstance(ts,str):
            dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
            if dt.tzinfo is None:
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            ts_ms=int(dt.timestamp()*1000)
        elif ts>10_000_000_000: ts_ms=int(ts)
        else: ts_ms=int(ts)*1000
        yield ts_ms, float(o["open"]), float(o["high"]), float(o["low"]), float(o["close"])

def main():
    lv = load_levels()
    am = (lv.get("am_box") or {})
    hi = am.get("high", lv.get("am_box_high"))
    lo = am.get("low",  lv.get("am_box_low"))
    if hi is None and lo is None:
        print("No AM box levels found in data/levels.json", file=sys.stderr); return
    print(f"[CANARY] using hi={hi} lo={lo}", flush=True)

    bar_csv = os.getenv("BAR_CSV")
    src = iter_csv(Path(bar_csv)) if bar_csv else iter_stdin()

    up=False; dn=False
    for ts,o,h,l,c in src:
        if (not up) and (hi is not None) and (h >= hi):
            up=True
            post_discord(f"🟡 CANARY: crossed AM HIGH {hi:.2f} (c={c:.2f})")
            print(f"[CANARY] posted HIGH at c={c}", flush=True)
        if (not dn) and (lo is not None) and (l <= lo):
            dn=True
            post_discord(f"🟡 CANARY: crossed AM LOW {lo:.2f} (c={c:.2f})")
            print(f"[CANARY] posted LOW at c={c}", flush=True)
        if up and dn:
            break

if __name__ == "__main__":
    main()
