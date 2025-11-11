#!/usr/bin/env python3
"""
Dry-run: simulate reading your live_minute.csv and show for each row
whether the strategy WOULD post and why. Replaces notify with a local
printer so no webhooks are touched.
Usage: python3 probes/dry_run_post_check.py /opt/sb-simple/data/live_minute.csv
"""
import sys, csv, time, importlib, traceback
from pathlib import Path

CSV = sys.argv[1] if len(sys.argv)>1 else "data/live_minute.csv"
CSV = Path(CSV)

if not CSV.exists():
    print("CSV not found:", CSV); sys.exit(1)

# ensure repo src is importable (adjust if needed)
ROOT = Path.cwd()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import sbwatch.strategy as stratmod
    importlib.reload(stratmod)
except Exception as e:
    print("Error importing strategy module:", e)
    traceback.print_exc()
    sys.exit(2)

# discover class
SBClass = getattr(stratmod, "SBEngine", None) or getattr(stratmod, "Strategy", None)
if SBClass is None:
    print("Could not find SBEngine/Strategy class in sbwatch.strategy"); sys.exit(3)

# instantiate (try safe constructor)
try:
    engine = SBClass({})
except TypeError:
    engine = SBClass()

# monkeypatch notify to see posts
class DummyNotify:
    @staticmethod
    def post_entry(**kw):
        print("DUMMY POST ATTEMPT:", kw)

# attach stub
try:
    engine._notify = DummyNotify()
except Exception:
    pass

# optional: reset dedupe var if exists (lets us see all potential posts)
if hasattr(engine, "_last_entry_ts"):
    engine._last_entry_ts = 0

print("Starting dry-run on", CSV)
with CSV.open() as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# helper to call on_bar with common signature variants
def call_on_bar(inst, ts_ms, o,h,l,c):
    if hasattr(inst, "on_bar"):
        try:
            return inst.on_bar(ts_ms=ts_ms, o=o, h=h, l=l, c=c)
        except TypeError:
            return inst.on_bar(ts_ms, o,h,l,c)
    # try other names
    for name in ("handle_bar","process_bar","onBar"):
        if hasattr(inst, name):
            f = getattr(inst,name)
            try:
                return f(ts_ms=ts_ms, o=o, h=h, l=l, c=c)
            except TypeError:
                return f(ts_ms, o,h,l,c)
    raise RuntimeError("no bar handler found")

# iterate rows and call
for i, r in enumerate(rows, start=1):
    try:
        ts = int(r.get("ts") or r.get("timestamp") or time.time()*1000)
        o = float(r.get("o") or r.get("open") or r.get("O"))
        h = float(r.get("h") or r.get("high") or r.get("H"))
        l = float(r.get("l") or r.get("low") or r.get("L"))
        c = float(r.get("c") or r.get("close") or r.get("C"))
    except Exception as e:
        print("Skipping row", i, "parse error:", e)
        continue
    print("--- ROW", i, "ts=", ts, "c=", c)
    try:
        call_on_bar(engine, ts, o,h,l,c)
    except Exception as e:
        print("Exception calling on_bar:", e)
        traceback.print_exc()
print("Dry-run complete.")
