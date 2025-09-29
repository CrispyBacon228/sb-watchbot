#!/usr/bin/env bash
set -euo pipefail

cd /opt/sb-watchbot

# pick the right python
PY="./.venv/bin/python"; [ -x "$PY" ] || PY=python3

# TRADE_DATE = calendar day whose Asia/London/NY sessions you want to replay
TRADE_DATE="${1:-$(date -u +%Y-%m-%d)}"

# Compute previous business day (Fri if Mon; skip weekends)
levels="$TRADE_DATE"
# previous calendar day first…
levels=$(date -u -d "$levels -1 day" +%Y-%m-%d)
# …then keep stepping back while weekend
while [ "$(date -u -d "$levels" +%u)" -ge 6 ]; do
  levels=$(date -u -d "$levels -1 day" +%Y-%m-%d)
done

echo "Trade date : $TRADE_DATE"
echo "Levels date: $levels (previous business day)"

# 1) Build levels for the previous business day (this writes ./data/levels.json)
"$PY" -m sbwatch.cli.main levels build --date "$levels"

# 2) Run replay for the trade date (it will use ./data/levels.json from step 1)
"$PY" -m sbwatch.cli.main replay run --date "$TRADE_DATE" ${REPLAY_FLAGS:-}

echo
echo "---- replay head (out/replay_${TRADE_DATE}.csv) ----"
head -n 20 "out/replay_${TRADE_DATE}.csv" || echo "no trades file"
