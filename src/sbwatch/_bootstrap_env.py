from __future__ import annotations
import os
try:
    from dotenv import load_dotenv
    # Load /opt/sb-watchbot/.env explicitly, then fallback to CWD
    load_dotenv("/opt/sb-watchbot/.env", override=False)
    load_dotenv(override=False)
except Exception:
    pass

# Optional: set process TZ if provided
tz = os.getenv("TZ")
if tz:
    os.environ["TZ"] = tz
