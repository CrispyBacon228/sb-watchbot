#!/usr/bin/env bash
set -euo pipefail

# Load env
if [ -f "/opt/sb-watchbot/.env" ]; then
  set -a; . /opt/sb-watchbot/.env; set +a
fi

webhook="${DISCORD_WEBHOOK_URL:-${DISCORD_WEBHOOK:-}}"
[ -z "$webhook" ] && webhook=""

live_state=$(systemctl is-active sb-live.service 2>/dev/null || true)
live_emoji=$([ "$live_state" = "active" ] && echo "✅" || echo "❌")

# Symbol: prefer env, else parse ExecStart
symbol="${FRONT_SYMBOL:-}"
if [ -z "$symbol" ]; then
  exec_line="$(systemctl show -p ExecStart sb-live.service 2>/dev/null | sed 's/^ExecStart=//')"
  symbol="$(echo "$exec_line" | sed -n 's/.*--symbol[[:space:]]\+\([^[:space:]]\+\).*/\1/p' 2>/dev/null || true)"
  [ -z "$symbol" ] && symbol="unknown"
fi

divisor="${PRICE_DIVISOR:-1000000000}"

last_err="$(sudo journalctl -u sb-live.service --since today 2>/dev/null \
  | grep -Ei 'error|traceback|exception' | tail -n 1 || true)"
[ -z "$last_err" ] && last_err="(none today)"

next_1010="$(systemctl list-timers --all 2>/dev/null | awk '/sb-live-status-1010\.timer/{print $2" UTC"}' | head -n1)"
next_1040="$(systemctl list-timers --all 2>/dev/null | awk '/sb-live-status-1040\.timer/{print $2" UTC"}' | head -n1)"
next_repl="$(systemctl list-timers --all 2>/dev/null | awk '/sb-replay-post\.timer/{print $2" UTC"}' | head -n1)"

content="**SB Watchbot Status**
${live_emoji} **Live Service:** \`${live_state}\`
**Symbol:** \`${symbol}\` • **Divisor:** \`${divisor}\`

**Last live error today:**
\`${last_err}\`

**Next timers:**
• 10:10 status → \`${next_1010:-n/a}\`
• 10:40 status → \`${next_1040:-n/a}\`
• Replay+post → \`${next_repl:-n/a}\`"

echo "----- STATUS BEGIN -----"
echo "$content"
echo "----- STATUS END -----"

# Post if webhook set and not in dry-run
if [ -n "$webhook" ] && [ "${DRY_RUN:-0}" != "1" ]; then
  curl -fsS -H "Content-Type: application/json" \
    -d "$(printf '{"content":%s}' "$(printf '%s' "$content" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")" \
    "$webhook" >/dev/null || echo "Discord post failed"
fi
