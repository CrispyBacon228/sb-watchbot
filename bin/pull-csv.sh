#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-simple
. .venv/bin/activate
PYTHONPATH=src \
CSV_START="${CSV_START:-09:55}" \
CSV_END="${CSV_END:-11:05}" \
SB_SYMBOL="NQZ5"
python -u src/sbwatch/tools/pull_csv.py

# --- SCALE_NQZ5_DIVISOR (auto-added) ---
# After pulling, scale the latest NQZ5 1m CSV's O/H/L/C by PRICE_DIVISOR so it matches live units.
if [ -n "${PRICE_DIVISOR:-}" ] && [ "${PRICE_DIVISOR}" != "1" ]; then
  CSV_NQZ5="$(ls -t data/csv/*NQZ5*_1m.csv 2>/dev/null | head -n 1 || true)"
  if [ -n "${CSV_NQZ5}" ] && [ -f "${CSV_NQZ5}" ]; then
    echo "Scaling NQZ5 CSV: ${CSV_NQZ5}  (PRICE_DIVISOR=${PRICE_DIVISOR})"
    CSV_PATH="${CSV_NQZ5}" PRICE_DIVISOR="${PRICE_DIVISOR}" python3 - <<'PY'
import csv, os, tempfile, shutil
p   = os.environ["CSV_PATH"]
div = float(os.environ.get("PRICE_DIVISOR","1e9"))
tmp = p + ".tmp"
with open(p, newline="") as f, open(tmp, "w", newline="") as g:
    r = csv.reader(f); w = csv.writer(g)
    hdr = next(r); w.writerow(hdr)
    for row in r:
        try:
            # ts, open, high, low, close, volume, ...
            row[1] = str(float(row[1]) / div)
            row[2] = str(float(row[2]) / div)
            row[3] = str(float(row[3]) / div)
            row[4] = str(float(row[4]) / div)
        except Exception:
            # non-numeric row — write back unchanged
            pass
        w.writerow(row)
shutil.move(tmp, p)
print("scaled:", p)
PY
    echo "Scale complete."
  else
    echo "No NQZ5 1m CSV found to scale (skipping)."
  fi
fi
# --- END SCALE_NQZ5_DIVISOR ---
