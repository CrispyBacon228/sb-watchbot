#!/usr/bin/env bash
set -euo pipefail
SRC="${1:?usage: sim_from_replay.sh out/replay_YYYY-MM-DD.csv}"
OUT="live/nq_1m.csv"
mkdir -p live
# start fresh
head -n 1 "$SRC" > "$OUT"
# stream rows into "live" one-by-one (0.4s cadence)
tail -n +2 "$SRC" | while IFS= read -r line; do
  printf '%s\n' "$line" >> "$OUT"
  sleep 0.4
done
