#!/usr/bin/env bash
set -euo pipefail

cd /opt/sb-watchbot
PY="./.venv/bin/python"; [ -x "$PY" ] || PY=python3

# Determine today's trade date in ET
export TZ=America/New_York
TRADE_DATE="$(date +%F)"
# previous calendar day
levels="$(date -d "$TRADE_DATE -1 day" +%F)"
# step back through weekends
while [ "$(date -d "$levels" +%u)" -ge 6 ]; do
  levels="$(date -d "$levels -1 day" +%F)"
done
unset TZ

echo "Live: building levels for $levels (prev business day), trade day $TRADE_DATE"

"$PY" -m sbwatch.cli.main levels build --date "$levels"
exec "$PY" -m sbwatch.cli.main live run
