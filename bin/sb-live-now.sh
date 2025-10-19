#!/usr/bin/env bash
set -euo pipefail
LOG=/opt/sb-simple/logs/live.log
ET=America/Indiana/Indianapolis
START=$(TZ=$ET date -d "+1 minute" +%H:%M)
END=$(TZ=$ET date -d "+4 minutes" +%H:%M)

# Ensure levels exist
/opt/sb-simple/.venv/bin/python /opt/sb-simple/sb_bot.py --build-levels >/opt/sb-simple/logs/levels.log 2>&1 || true

# Print loaded levels into the log for visibility
/opt/sb-simple/.venv/bin/python - <<'PY' >>"$LOG" 2>&1
import json, datetime
from pathlib import Path
p=Path("/opt/sb-simple/data/levels.json")
if p.exists():
    d=json.loads(p.read_text())["levels"]
    print(f"[CHECK] Loaded levels -> box_high={d.get('box_high'):.2f} box_low={d.get('box_low'):.2f} "
          f"pdh={d.get('pdh'):.2f} pdl={d.get('pdl'):.2f} "
          f"asia_high={d.get('asia_high','-')} asia_low={d.get('asia_low','-')} "
          f"london_high={d.get('london_high','-')} london_low={d.get('london_low','-')}")
else:
    print("[CHECK] levels.json not found")
PY

# Temporarily override the live window in .env
sed -i '/^LIVE_START=/d;/^LIVE_END=/d' /opt/sb-simple/.env
printf "LIVE_START=%s\nLIVE_END=%s\n" "$START" "$END" >> /opt/sb-simple/.env

echo "[CHECK] Starting live from $START to $END (ET) ..." >>"$LOG"

# Run live and stream output into the log
stdbuf -oL -eL /opt/sb-simple/.venv/bin/python /opt/sb-simple/sb_bot.py --live >>"$LOG" 2>&1 || true

# Cleanup overrides
sed -i '/^LIVE_START=/d;/^LIVE_END=/d' /opt/sb-simple/.env
echo "[CHECK] Live run finished." >>"$LOG"
