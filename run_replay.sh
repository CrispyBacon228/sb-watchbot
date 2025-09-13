#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-watchbot

DATE="${1:-2025-09-12}"  # default; or pass like: ./run_replay.sh 2025-09-12

echo "▶ Using REPLAY_ET_DATE=${DATE}"

# Build levels
sudo env $(grep -v '^#' .env | xargs) REPLAY_ET_DATE="${DATE}" \
  PYTHONUNBUFFERED=1 python3 scripts/build_levels.py || true

# Replay
sudo env $(grep -v '^#' .env | xargs) REPLAY_ET_DATE="${DATE}" \
  PYTHONUNBUFFERED=1 python3 scripts/replay_core.py
