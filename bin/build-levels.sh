#!/usr/bin/env bash
set -euo pipefail
REPO="/opt/sb-simple"; [ -d "$REPO" ] || REPO="/opt/sb-watchbot"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
cd "$REPO"

# Load env (for session settings etc.)
if [ -f /etc/sb-watchbot.env ]; then
  set -a; source /etc/sb-watchbot.env; set +a
fi

export PYTHONUNBUFFERED=1
export PYTHONPATH=src

if [ -f "sb_bot.py" ]; then
  exec "$PY" sb_bot.py --build-levels
else
  exec "$PY" -m sbwatch.sb_bot --build-levels
fi
