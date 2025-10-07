#!/usr/bin/env bash
set -euo pipefail
LOG="/opt/sb-watchbot/out/live_status.log"
mkdir -p /opt/sb-watchbot/out

# Load env inside the script so oneshot services have the webhook
set -a; source /etc/sb-watchbot/env; set +a

MSG="${1:-SB status heartbeat}"
# Only send on weekdays between 10:00 and 11:00 ET
NOW_ET=$(TZ=America/New_York date +%H:%M)
DOW=$(TZ=America/New_York date +%u)   # 1..5
printf '%s | DOW=%s NOW_ET=%s MSG="%s"\n' "$(date -u '+%F %T UTC')" "$DOW" "$NOW_ET" "$MSG" >> "$LOG"

if [ "$DOW" -ge 1 ] && [ "$DOW" -le 5 ] && [[ "$NOW_ET" > "10:00" && "$NOW_ET" < "11:01" ]]; then
  PAYLOAD=$(printf '{"content":"%s"}' "$MSG")
  CODE=$(curl -s -o /dev/null -w '%{http_code}' \
          -H 'Content-Type: application/json' \
          -X POST -d "$PAYLOAD" "$DISCORD_WEBHOOK" || true)
  echo "$(date -u '+%F %T UTC') | curl_code=$CODE" >> "$LOG"
else
  echo "$(date -u '+%F %T UTC') | skipped (outside window or weekend)" >> "$LOG"
fi
