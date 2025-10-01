#!/usr/bin/env bash
set -euo pipefail
set -a; . ./.env; set +a

mkdir -p out

# Run the live watcher, mirror to file & console, and forward alert lines to Discord.
python -m sbwatch.app.live_watch \
| tee -a out/live_watch.log \
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
