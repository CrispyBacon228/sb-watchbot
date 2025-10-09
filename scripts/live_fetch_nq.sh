#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/sb-watchbot/.venv/bin:$PATH"
: "${DATABENTO_API_KEY:?DATABENTO_API_KEY not set}"

SYM="${SYM:-NQ*}"
OUT="live/nq_1m.csv"
TMP_RAW="${OUT}.raw.tmp"
TMP_NORM="${OUT}.norm.tmp"

mkdir -p live out

while true; do
  DAY=$(date +%F)

  # 1) fetch to TMP_RAW (Databento CLI)
  databento timeseries get \
    --dataset=GLBX.MDP3 \
    --schema=ohlcv-1m \
    --symbols="$SYM" \
    --start="${DAY} 09:30:00 America/New_York" \
    --end="now America/New_York" \
    --compression=none \
    --stitch=legacy \
    --out="$TMP_RAW" >/dev/null 2>&1 || true

  # 2) normalize → TMP_NORM only if we actually got rows
  if [[ -s "$TMP_RAW" ]]; then
    python - <<'PY' "$TMP_RAW" "$TMP_NORM"
import sys, pandas as pd, os
src, dst = sys.argv[1], sys.argv[2]
if not os.path.exists(src) or os.path.getsize(src)==0: raise SystemExit(0)
df = pd.read_csv(src)
df.columns = [c.lower() for c in df.columns]
if "timestamp" not in df.columns:
    for c in ("ts","time","datetime","date"):
        if c in df.columns:
            df.rename(columns={c:"timestamp"}, inplace=True)
            break
df = df[["timestamp","open","high","low","close","volume"]].dropna()
df.to_csv(dst, index=False)
PY

    # 3) price sanity on last row (avoid double scaling)
    if [[ -s "$TMP_NORM" ]]; then
      LAST_CLOSE="$(tail -n1 "$TMP_NORM" | awk -F, '{print $5}')"
      python - "$LAST_CLOSE" <<'PY' || { echo "$(date -Iseconds) ⚠️ bad scale (skip write)" | tee -a out/live-fetch.log; rm -f "$TMP_NORM"; sleep 5; continue; }
import sys
v=float(sys.argv[1])
assert 5000 < v < 200000
PY || { echo "$(date -Iseconds) ⚠️ bad scale (skip write)" | tee -a out/live-fetch.log; rm -f "$TMP_NORM"; sleep 5; continue; }
import sys
v=float(sys.argv[1])
assert 5000 < v < 200000
PY
      # 4) atomic replace
      mv -f "$TMP_NORM" "$OUT"
      echo "$(date -Iseconds) wrote $(wc -l <"$OUT") rows → $OUT" | tee -a out/live-fetch.log
    fi
    rm -f "$TMP_RAW"
  fi

  sleep 5
done
