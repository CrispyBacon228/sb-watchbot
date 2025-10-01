#!/usr/bin/env bash
set -euo pipefail
DATE="${1:-$(date -u +%F)}"
source .venv/bin/activate
python -m sbwatch.app.replay_day "$DATE"
