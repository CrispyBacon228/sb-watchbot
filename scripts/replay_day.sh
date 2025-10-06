#!/usr/bin/env bash
set -euo pipefail
DATE="${1:-$(TZ=America/New_York date +%F)}"
set -a; source /etc/sb-watchbot/env; set +a
source /opt/sb-watchbot/.venv/bin/activate
mkdir -p out
python -m sbwatch.app.replay_day --date "$DATE" --start-et "09:30" --end-et "11:05"
