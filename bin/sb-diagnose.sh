#!/usr/bin/env bash
set -euo pipefail
OUT="out/diagnostics-$(date +%F_%H%M%S).log"
mkdir -p out
{
  echo "===== SB DIAGNOSTICS $(date -Iseconds) ====="
  echo "pwd: $(pwd)"
  echo "python: $(command -v python || true)"
  python -V 2>&1 || true

  echo; echo "== ENV SNAPSHOT ==";
  sudo sh -c 'grep -E "^(DISCORD_WEBHOOK|DATABENTO_API_KEY|SYM|TZ)=" /etc/sb-watchbot/env 2>/dev/null | sed "s/=\(.\{4\}\).*/=\1********/" || true'

  echo; echo "== UNIT SETTINGS ==";
  for u in sb-live-fetch.service sb-live.service; do
    echo "-- $u --"
    sudo systemctl cat $u 2>/dev/null | grep -E "^\[Service\]|ExecStart=|WorkingDirectory=|EnvironmentFile=" || echo "unit not found"
  done

  echo; echo "== SERVICE STATUS ==";
  sudo systemctl is-active sb-live-fetch.service 2>/dev/null || true
  sudo systemctl is-active sb-live.service 2>/dev/null || true
  sudo systemctl show -p NRestarts sb-live-fetch.service sb-live.service 2>/dev/null || true

  echo; echo "== JOURNAL TAILS ==";
  sudo journalctl -u sb-live-fetch.service -n 120 --no-pager 2>/dev/null || true
  sudo journalctl -u sb-live.service -n 120 --no-pager 2>/dev/null || true

  echo; echo "== CSV SANITY ==";
  CSV="live/nq_1m.csv"
  if [ -s "$CSV" ]; then
    echo "CSV exists: $CSV lines=$(wc -l <"$CSV")"
    tail -n 3 "$CSV"
    LAST_TS=$(tail -n1 "$CSV" | cut -d, -f1)
    LAST_CLOSE=$(tail -n1 "$CSV" | cut -d, -f5)
    NOW=$(date +%s)
    to_epoch(){ TS="$1"; case "$TS" in *T*Z|*-*-*) date -d "$TS" +%s 2>/dev/null || echo 0 ;; *) [ ${#TS} -gt 10 ] && echo $((TS/1000)) || echo "$TS" ;; esac; }
    LAST_EPOCH=$(to_epoch "$LAST_TS"); AGE=$((NOW - LAST_EPOCH))
    echo "Last TS: $LAST_TS (age ${AGE}s)"
    python - <<PY
v=float("$LAST_CLOSE")
print("Last close:", v)
print("PRICE_OK" if (5000 < v < 200000) else "PRICE_BAD")
PY
    [ "$AGE" -le 600 ] && echo "FRESH_OK" || echo "FRESH_BAD"
  else
    echo "CSV_MISSING"
  fi

  echo; echo "== ONE-SHOT STRATEGY =="
  source .venv/bin/activate 2>/dev/null || true
  PYTHONPATH=. python -m sbwatch.app.live_sb --csv "$CSV" --ignore-clock --heartbeat --once 2>&1 | tail -n 60 || echo "LIVE_SB_FAIL"

  echo; echo "== SUMMARY =="
  # Simple PASS/FAIL lines the eye can catch
  grep -q "PRICE_OK" "$OUT" 2>/dev/null || true
} | tee "$OUT"

echo "=== WROTE $OUT ==="
