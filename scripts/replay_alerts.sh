#!/usr/bin/env bash
set -euo pipefail
set -a; . ./.env; set +a

DATE="${1:-$(date -u +%F)}"
mkdir -p out

CSV="out/replay_${DATE}.csv"

# 1. Generate replay CSV if not already built
if [ ! -s "$CSV" ]; then
  echo "Building $CSV..."
  ./scripts/replay_day.sh "$DATE"
fi

# 2. Run replay alerts against the CSV
python -m sbwatch.app.replay_alerts --csv "$CSV" \
| tee "out/replay_alerts_${DATE}.log" \
| while IFS= read -r line; do
  case "$line" in
    "[ALERT]"*|"SB ENTRY "*|"[ALERT] SB ENTRY "*)
      if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
        payload=$(printf '{"content":"%s"}' "$(echo "$line" | sed 's/"/\\"/g')")
        curl -fsS -H "Content-Type: application/json" -d "$payload" "$DISCORD_WEBHOOK_URL" >/dev/null || true
      fi
      ;;
  esac
  echo "$line"
done
