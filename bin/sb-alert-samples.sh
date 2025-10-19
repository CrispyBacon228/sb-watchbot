#!/usr/bin/env bash
set -euo pipefail
WEBHOOK="$(grep '^DISCORD_WEBHOOK=' /opt/sb-simple/.env | cut -d= -f2-)"
[ -n "$WEBHOOK" ] || { echo "No DISCORD_WEBHOOK"; exit 1; }
send(){ curl -s -H "Content-Type: application/json" -d @- "$WEBHOOK" >/dev/null; sleep 0.4; }
send <<'J'{"content":"📐 **SB Levels built** (sample)"}J
send <<'J'{"content":"🟡 **SB Live waiting** (sample)"}J
send <<'J'{"content":"🟢 **SB Live started** (sample)"}J
send <<'J'{"content":"🟢 **SB Long** Entry 24720.25 SL 24660.00 TP1 24780.50 TP2 24840.75"}J
send <<'J'{"content":"🔴 **SB Short** Entry 24955.25 SL 25015.50 TP1 24895.00 TP2 24834.75"}J
send <<'J'{"content":"⏹️ **SB Live ended** (sample)"}J
echo "✅ Sample alerts sent."
