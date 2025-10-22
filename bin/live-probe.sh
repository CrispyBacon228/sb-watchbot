#!/usr/bin/env bash
set -euo pipefail
REPO="/opt/sb-simple"; [ -d "$REPO" ] || REPO="/opt/sb-watchbot"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
cd "$REPO"
[ -f /etc/sb-watchbot.env ] && { set -a; source /etc/sb-watchbot.env; set +a; }
export PYTHONUNBUFFERED=1
exec "$PY" bin/live-probe.py
