#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-watchbot
export PYTHONPATH=/opt/sb-watchbot/src:$PYTHONPATH
source .venv/bin/activate
exec python -m sbwatch.app.live --symbol "${SYMBOL:-NQ}" --poll "${POLL_SECONDS:-5}"
