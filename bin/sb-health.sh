#!/bin/sh
# POSIX-safe lite audit; never exits early
export PYTHONPATH=/opt/sb-simple

echo "=== SB Watchbot Health ($(date -Is)) ==="

# 1) Paths
for d in /opt/sb-simple /opt/sb-simple/data /opt/sb-simple/logs; do
  if [ -d "$d" ]; then
    echo "OK  Dir ok: $d"
  else
    mkdir -p "$d" 2>/dev/null && echo "OK  Created dir: $d" || echo "FAIL Cannot create dir: $d"
  fi
done
echo

# 2) .env (masked)
ENV=/opt/sb-simple/.env
if [ -f "$ENV" ]; then
  DB_API_KEY=$(grep -E '^DB_API_KEY=' "$ENV" | cut -d= -f2- 2>/dev/null)
  DISCORD_WEBHOOK=$(grep -E '^DISCORD_WEBHOOK=' "$ENV" | cut -d= -f2- 2>/dev/null)
  DATASET=$(grep -E '^DATASET=' "$ENV" | cut -d= -f2- 2>/dev/null)
  SCHEMA=$(grep -E '^SCHEMA=' "$ENV" | cut -d= -f2- 2>/dev/null)
  SYMBOL=$(grep -E '^SYMBOL=' "$ENV" | cut -d= -f2- 2>/dev/null)
  [ -n "$DB_API_KEY" ] && echo "OK  DB_API_KEY present (masked: ${DB_API_KEY%????????????????????????????????????????})…" || echo "FAIL .env missing DB_API_KEY"
  [ -n "$DISCORD_WEBHOOK" ] && echo "OK  DISCORD_WEBHOOK present" || echo "WARN .env missing DISCORD_WEBHOOK"
  [ -n "$DATASET" ] && echo "OK  DATASET=$DATASET" || echo "WARN DATASET not set"
  [ -n "$SCHEMA" ] && echo "OK  SCHEMA=$SCHEMA"   || echo "WARN SCHEMA not set"
  [ -n "$SYMBOL" ] && echo "OK  SYMBOL=$SYMBOL"   || echo "WARN SYMBOL not set"
else
  echo "FAIL No .env at $ENV"
fi
echo

# 3) Python venv + deps
VENV=/opt/sb-simple/.venv
if [ -x "$VENV/bin/python" ]; then
  MISSING=$("$VENV/bin/python" - <<'PY' 2>/dev/null || true
import pkgutil
need = ["databento","dotenv","requests","pytz"]
missing=[m for m in need if pkgutil.find_loader(m) is None]
print(",".join(missing))
PY
)
  if [ -z "$MISSING" ]; then echo "OK  Python deps installed"; else echo "FAIL Missing python deps: $MISSING"; fi
else
  echo "FAIL Python venv missing at $VENV"
fi
echo

# 4) Code checks
BOT=/opt/sb-simple/sb_bot.py
if [ -f "$BOT" ]; then
  grep -q 'PRICE_DIVISOR *= *1e9' "$BOT" && echo "OK  PRICE_DIVISOR=1e9" || echo "FAIL PRICE_DIVISOR not 1e9"
  grep -q 'def live_run' "$BOT" && echo "OK  live_run() present" || echo "FAIL live_run() missing"
else
  echo "FAIL sb_bot.py missing at $BOT"
fi
echo

# 5) systemd unit files + timers enabled
[ -f /etc/systemd/system/sb-levels.service ] && echo "OK  unit: sb-levels.service exists" || echo "WARN no unit: sb-levels.service"
[ -f /etc/systemd/system/sb-live.service   ] && echo "OK  unit: sb-live.service exists"   || echo "WARN no unit: sb-live.service"
[ -f /etc/systemd/system/sb-levels.timer   ] && echo "OK  unit: sb-levels.timer exists"   || echo "WARN no unit: sb-levels.timer"
[ -f /etc/systemd/system/sb-live.timer     ] && echo "OK  unit: sb-live.timer exists"     || echo "WARN no unit: sb-live.timer"
systemctl is-enabled sb-levels.timer >/dev/null 2>&1 && echo "OK  timer enabled: sb-levels.timer" || echo "WARN timer not enabled: sb-levels.timer"
systemctl is-enabled sb-live.timer   >/dev/null 2>&1 && echo "OK  timer enabled: sb-live.timer"   || echo "WARN timer not enabled: sb-live.timer"
echo

# 6) Levels preview
LV=/opt/sb-simple/data/levels.json
if [ -f "$LV" ]; then
  echo "OK  levels.json present"
  awk 'BEGIN{h=0}
/"levels":/{h=1;next}
h && /}/ {h=0}
h && /box_high|box_low|pdh|pdl|asia_high|asia_low|london_high|london_low/ {
  gsub(/[,"]/,""); gsub(/^[ \t]+/,""); print "   -",$0
}' "$LV" 2>/dev/null
else
  echo "WARN levels.json not found (run: sb_bot.py --build-levels on a market day)"
fi
echo

# 7) Databento REST test (older window to avoid 422)
echo "--- Databento REST check (now-22m → now-12m) ---"
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" - <<'PY' 2>/dev/null || true
import datetime as dt, sys
sys.path.append("/opt/sb-simple")
try:
    from sb_bot import ET, fetch_ohlcv_1m
    now = dt.datetime.now(tz=ET)
    start = (now - dt.timedelta(minutes=22)).replace(second=0, microsecond=0)
    end   = (now - dt.timedelta(minutes=12)).replace(second=0, microsecond=0)
    bars = fetch_ohlcv_1m(start, end)
    print(f"Fetched {len(bars)} bars between {start} and {end}")
    for c in bars[-3:]:
        print(c.ts.strftime("%H:%M"), f"O:{c.o:.2f} H:{c.h:.2f} L:{c.l:.2f} C:{c.c:.2f} V:{c.v}")
except Exception as e:
    print("REST check error:", e)
PY
fi
echo "--- Databento REST check (now-20m → now-10m) ---"
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" - <<'PY' 2>/dev/null || true
import datetime as dt, sys
sys.path.append("/opt/sb-simple")
try:
    from sb_bot import ET, fetch_ohlcv_1m
    now = dt.datetime.now(tz=ET)
    start = (now - dt.timedelta(minutes=20)).replace(second=0, microsecond=0)
    end   = (now - dt.timedelta(minutes=10)).replace(second=0, microsecond=0)
    bars = fetch_ohlcv_1m(start, end)
    print(f"Fetched {len(bars)} bars between {start} and {end}")
    for c in bars[-3:]:
        print(c.ts.strftime("%H:%M"), f"O:{c.o:.2f} H:{c.h:.2f} L:{c.l:.2f} C:{c.c:.2f} V:{c.v}")
except Exception as e:
    print("REST check error:", e)
PY
fi
echo

# 8) Databento Live probe (1 bar)
echo "--- Databento Live probe (1 bar) ---"
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" - <<'PY' 2>/dev/null || true
import sys
sys.path.append("/opt/sb-simple")
try:
    from databento import Live
    from sb_bot import record_to_candle, DATASET, SCHEMA, SYMBOL
    key = [l.split("=",1)[1].strip() for l in open("/opt/sb-simple/.env") if l.startswith("DB_API_KEY=")][0]
    cli = Live(key)
    cli.subscribe(dataset=DATASET, schema=SCHEMA, symbols=[SYMBOL])
    for m in cli:
        c = record_to_candle(m)
        if c:
            print("LIVE BAR:", c.ts.strftime("%H:%M"), f"O:{c.o:.2f} H:{c.h:.2f} L:{c.l:.2f} C:{c.c:.2f} V:{c.v}")
            break
except Exception as e:
    print("Live probe error:", e)
PY
fi

echo
echo "=== Audit complete ==="
