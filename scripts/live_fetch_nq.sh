#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/sb-watchbot/.venv/bin:$PATH"
: "${DATABENTO_API_KEY:?DATABENTO_API_KEY not set}"

SYM="${SYM:-NQ*}"
OUT="live/nq_1m.csv"
TMP_RAW="${OUT}.raw.tmp"
TMP_NORM="${OUT}.norm.tmp"

mkdir -p live

while true; do
  DAY=$(date +%F)

  # 1) fetch to TMP_RAW
  databento timeseries get \
    --dataset=GLBX.MDP3 \
    --schema=ohlcv-1m \
    --symbols="$SYM" \
    --start="${DAY} 09:30:00 America/New_York" \
    --end="now America/New_York" \
    --compression=none \
    --stitch=legacy \
    --out="$TMP_RAW" >/dev/null 2>&1 || true

  # 2) normalize -> TMP_NORM (only if TMP_RAW exists)
  if [[ -s "$TMP_RAW" ]]; then
    python - <<'PY' "$TMP_RAW" "$TMP_NORM"
import sys, pandas as pd, os
src, dst = sys.argv[1], sys.argv[2]
if not os.path.exists(src) or os.path.getsize(src)==0:
    raise SystemExit(0)
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
    # 3) atomically replace OUT
    mv -f "$TMP_NORM" "$OUT" || true
    rm -f "$TMP_RAW"
  fi

  sleep 5
done
