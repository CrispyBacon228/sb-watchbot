#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-watchbot
source .venv/bin/activate

DATE_ET="${1:-$(TZ=America/New_York date +%F)}"
OUT_DIR="./out"
mkdir -p "$OUT_DIR"

echo "Running replay for $DATE_ET..."
python -m sbwatch.cli.main replay run --date "$DATE_ET" --out "$OUT_DIR" --no-wick-only

echo "Replay finished. Alerts (if any):"
if [ -f "$OUT_DIR/replay_${DATE_ET}.csv" ]; then
  column -t -s, "$OUT_DIR/replay_${DATE_ET}.csv" | sed -n '1,200p'
else
  echo "No CSV found."
fi
