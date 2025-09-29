import inspect, importlib.util
from pathlib import Path

try:
    from sbwatch.strategy.ict import ICTDetector
except Exception as e:
    print("❌ Failed to import ICTDetector:", e)
    raise

src = inspect.getsourcefile(ICTDetector) or "<unknown>"
print("✅ ICTDetector path:", Path(src).resolve())

expected_suffix = "sbwatch/strategy/ict.py"
if not str(Path(src)).endswith(expected_suffix):
    raise SystemExit(f"❌ Wrong ICT path loaded: {src} (expected suffix .../{expected_suffix})")

print("✅ Sanity OK")
