import sys, datetime as dt
from zoneinfo import ZoneInfo

# ✅ ensure sb-simple src is importable
if "/opt/sb-simple/src" not in sys.path:
    sys.path.insert(0, "/opt/sb-simple/src")

import sbwatch.notify as notify
from sbwatch.strategy import SBEngine

# monkeypatch discord sender so it doesn't actually post
def _printer(msg: str):
    print("\n=== DISCORD OUTPUT (SIMULATED) ===")
    print(msg)
    print("==================================\n")

notify.post_discord = _printer

engine = SBEngine(levels={})

ET = ZoneInfo("America/New_York")
ts = dt.datetime.now(tz=ET).replace(hour=10, minute=5, second=0, microsecond=0)
ts_ms = int(ts.timestamp() * 1000)

engine._maybe_post(ts_ms, "long", 20150.25, sl=20100.00, tp=20210.50, disp="TEST SWEEP")
notify.post_entry("long", 20150.25, 20100.00, 20210.50, "TEST SWEEP", when=ts_ms)
