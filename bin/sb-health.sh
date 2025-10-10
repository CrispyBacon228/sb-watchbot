#!/usr/bin/env bash
cd /opt/sb-watchbot || exit 1
echo "=== SB Watchbot Health Check ==="
for svc in sb-live-fetch.service sb-live.service; do
  echo; echo "--- $svc ---"
  sudo systemctl is-active "$svc" >/dev/null && echo "✓ $svc running" || echo "✗ $svc down"
done

CSV="live/nq_1m.csv"
if [ -s "$CSV" ]; then
  echo; echo "--- CSV ---"
  LINES=$(wc -l <"$CSV")
  LAST=$(tail -n1 "$CSV" | cut -d, -f1)
  AGE=$(( $(date +%s) - $(date -d "${LAST/T/ }" +%s) ))
  echo "Rows: $LINES | Last TS: $LAST | Age ${AGE}s"
  python - <<PY
v=float("$(tail -n1 $CSV | cut -d, -f5)")
assert 5000 < v < 200000
print("Price scale OK:", v)
PY
else
  echo "CSV missing or empty!"
fi
echo "=== End ==="
