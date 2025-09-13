#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [[ ! -f scripts/build_levels.py ]]; then
  echo "scripts/build_levels.py not found"; exit 2
fi
: "${REPLAY_ET_DATE:?REPLAY_ET_DATE not set (export REPLAY_ET_DATE=YYYY-MM-DD)}"
python3 -X dev -W default scripts/build_levels.py
