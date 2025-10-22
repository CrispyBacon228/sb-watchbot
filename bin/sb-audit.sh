#!/usr/bin/env bash
set -euo pipefail
cd /opt/sb-simple

echo "=== SB Watchbot Audit ($(date -Is)) ==="
echo
echo "[Repo]"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && {
  git remote -v | sed 's/^/  /'
  git --no-pager log -1 --pretty='  %h %ci  %s'
} || echo "  (not a git repo)"

echo
echo "[Python compile]"
/opt/sb-simple/.venv/bin/python -m py_compile sb_bot.py && echo "  sb_bot.py OK" || true

echo
echo "[Env]"
awk -F= '
  $1=="DB_API_KEY"{print "  DB_API_KEY=***"substr($2,length($2)-4)}
  $1=="DISCORD_WEBHOOK"{print "  DISCORD_WEBHOOK=***"substr($2,length($2)-8)}
  $1=="SEND_LEVELS_ALERT"{print "  SEND_LEVELS_ALERT="$2}
' .env 2>/dev/null || echo "  .env missing?"

echo
echo "[Systemd]"
systemctl cat sb-levels.service | sed 's/^/  /' | head -n 20 || true
systemctl cat sb-live.service   | sed 's/^/  /' | head -n 20 || true
echo
systemctl list-timers | grep -E 'sb-(levels|live)' | sed 's/^/  /' || true

echo
echo "[Levels file]"
if [ -f data/levels.json ]; then
  stat -c "  mtime: %y (UTC)" data/levels.json
  /opt/sb-simple/.venv/bin/python - <<'PY'
import json; d=json.load(open("data/levels.json"))
print("  date:", d.get("date"))
ks=list(d.get("levels",{}).keys())
print("  keys:", ", ".join(sorted(ks)))
for k in ("pdh","pdl","asia_high","asia_low","london_high","london_low"):
    v=d["levels"].get(k)
    if v is not None:
        print(f"   {k:12s} {v}")
PY
else
  echo "  data/levels.json not found."
fi

echo
echo "[Databento REST probe (safe window)]"
# 12-min lag window to avoid 'too fresh' errors
/opt/sb-simple/.venv/bin/python - <<'PY'
import os, datetime as dt
from sb_bot import ET, fetch_ohlcv_1m_safe
now=dt.datetime.now(ET)
start=now-dt.timedelta(minutes=22)
end  =now-dt.timedelta(minutes=10)
try:
    cs=fetch_ohlcv_1m_safe(start, end)
    lo=min(c.l for c in cs); hi=max(c.h for c in cs)
    print(f"  bars={len(cs)}  HI {hi}@{cs[-1].ts if cs else 'n/a'}  LO {lo}")
except Exception as e:
    print("  REST error:", e)
PY

echo
echo "[2-min live probe (no alerts; no Discord)]"
LIVE_START=$(date -u -d '60 seconds' +%H:%M)
LIVE_END=$(date -u -d '180 seconds' +%H:%M)
( set -a; . ./.env; SEND_LEVELS_ALERT=false; set +a;
/opt/sb-simple/.venv/bin/python - <<PY
import os, datetime as dt, time
from sb_bot import ET, levels_cmd
os.environ["LIVE_START"]="${LIVE_START}"
os.environ["LIVE_END"]="${LIVE_END}"
print(f"  live window (UTC): ${LIVE_START}-${LIVE_END}")
try:
    levels_cmd()  # your code prints [BAR] lines as they arrive; ends automatically
    print("  live probe finished.")
except Exception as e:
    print("  live error:", e)
PY
) || true

echo
echo "[Journal — last levels run]"
journalctl -u sb-levels.service -n 50 --no-pager | sed 's/^/  /' || true

echo
echo "=== Audit complete ==="
