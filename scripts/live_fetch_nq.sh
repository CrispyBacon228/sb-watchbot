#!/usr/bin/env bash
set -euo pipefail
mkdir -p live out
CSV="live/nq_1m.csv"
TMP="$(mktemp)"

# Call the original fetcher; it should print CSV to stdout.
# If your original writes to a file instead, edit it to honor CSV="$TMP" and write there.
if ! bash scripts/live_fetch_nq.sh.bak > "$TMP"; then
  echo "$(date -Iseconds) ERROR fetch exited nonzero" | tee -a out/live-fetch.log
  rm -f "$TMP"; exit 1
fi

# Require at least one data row (not just header)
if ! grep -qE '^[0-9]' "$TMP"; then
  echo "$(date -Iseconds) ⚠️ no data (skip write)" | tee -a out/live-fetch.log
  rm -f "$TMP"; exit 0
fi

# Price sanity (avoid double-scaling)
LAST_CLOSE="$(tail -n1 "$TMP" | awk -F, '{print $5}')"
python3 - "$LAST_CLOSE" <<'PY' || { echo "$(date -Iseconds) ⚠️ bad scale (skip write)"; rm -f "$TMP"; exit 0; }
import sys
v=float(sys.argv[1])
assert 5000 < v < 200000
PY

# Atomic replace
mv -f "$TMP" "${CSV}.tmp"
mv -f "${CSV}.tmp" "$CSV"
echo "$(date -Iseconds) wrote $(wc -l <"$CSV") rows → $CSV" | tee -a out/live-fetch.log
