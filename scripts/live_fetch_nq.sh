#!/usr/bin/env bash
set -euo pipefail
SYM="${SYM:-NQ*}"                 # set to NQZ5 if you prefer
OUT="live/nq_1m.csv"
while true; do
  DAY=$(date +%F)
  databento timeseries get \
    --dataset=GLBX.MDP3 \
    --schema=ohlcv-1m \
    --symbols="$SYM" \
    --start="${DAY} 09:30:00 America/New_York" \
    --end="now America/New_York" \
    --compression=none \
    --stitch=legacy \
    --out="$OUT.tmp" >/dev/null 2>&1 || true

  # Normalize headers to expected names
  python - <<'PY' "$OUT.tmp" "$OUT"
import sys, pandas as pd, os
tmp, out = sys.argv[1], sys.argv[2]
if not os.path.exists(tmp): sys.exit(0)
df = pd.read_csv(tmp)
df.columns = [c.lower() for c in df.columns]
if "timestamp" not in df.columns:
    for c in ("ts","time","datetime","date"):
        if c in df.columns: df.rename(columns={c:"timestamp"}, inplace=True); break
df = df[["timestamp","open","high","low","close","volume"]].dropna()
df.to_csv(out, index=False)
PY
  mv -f "$OUT" "$OUT"
  sleep 5
done
