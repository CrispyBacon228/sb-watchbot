#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-watchbot
source .venv/bin/activate

# Skip weekends (1=Mon ... 7=Sun in ET)
TZ="America/New_York" dow=$(date +%u)
if [[ "$dow" -gt 5 ]]; then
  echo "Weekend; skipping."
  exit 0
fi

date_et=$(TZ="America/New_York" date +%Y-%m-%d)
echo "Running AM replay for ${date_et}"

sbwatch build-levels --date "${date_et}"
sbwatch replay "${date_et}" --verbose
