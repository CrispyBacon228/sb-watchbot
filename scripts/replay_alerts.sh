#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate

CSV=""
SPEED=0
QUIET=""
DATE_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv) CSV="$2"; shift 2 ;;
    --speed) SPEED="$2"; shift 2 ;;
    --quiet) QUIET="--quiet"; shift ;;
    -h|--help) echo "usage: $0 [YYYY-MM-DD] [--csv PATH] [--speed N] [--quiet]"; exit 0;;
    *) DATE_ARG="$1"; shift ;;
  esac
done

if [[ -n "$CSV" ]]; then
  # CSV mode: do not rebuild a day; just replay the CSV you gave me
  echo "Replaying CSV: $CSV"
  python -m sbwatch.app.replay_alerts --csv "$CSV" --speed "$SPEED" $QUIET
else
  if [[ -z "${DATE_ARG:-}" ]]; then
    echo "error: pass a date (YYYY-MM-DD) or --csv PATH"
    exit 1
  fi
  # DATE mode: build day CSV, then replay it
  echo "Building day CSV for DATE=$DATE_ARG..."
  python -m sbwatch.app.replay_day "$DATE_ARG"
  python -m sbwatch.app.replay_alerts --csv "out/replay_${DATE_ARG}.csv" --speed "$SPEED" $QUIET
fi
