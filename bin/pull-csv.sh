#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-simple
. .venv/bin/activate
PYTHONPATH=src \
CSV_START="${CSV_START:-09:55}" \
CSV_END="${CSV_END:-11:05}" \
SB_SYMBOL="${SB_SYMBOL:-NQ}" \
python -u src/sbwatch/tools/pull_csv.py
