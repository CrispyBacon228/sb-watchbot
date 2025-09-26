# SB Watchbot

SB Watchbot is an automated market monitoring system for ICT-style trading strategies.  
It generates daily levels, watches live markets, and pushes trade alerts to Discord.

## Features
- Daily levels (Asia, London, PDH/PDL) → saved to `./data/levels.json`
- ICT strategy alerts:
  - Detects liquidity sweeps + Fair Value Gaps
  - Entry rules limited to 10–11 ET kill zone
  - Take profit and stop-loss targets auto-calculated
  - Alerts filtered to avoid overlap
- Outputs alerts to:
  - Discord (via webhook)
  - CSV logs in `./out`

## Usage

### Replay a day
```bash
python -m sbwatch.cli.main ict replay --date 2025-09-25 --out ./out
Run live watcher
bash
Copy code
python -m sbwatch.cli.main live run
Check alerts
bash
Copy code
column -s, -t ./out/alerts_live_<DATE>.csv | tail -n 20
Environment
.env should include:

ini
Copy code
DATABENTO_API_KEY=yourkey
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx/yyyy
POLL_SECONDS=5
COOLDOWN_SEC=300
MARGIN_SEC=900
Service
Installed as sb-watchbot.service + sb-watchbot-levels.timer

bash
Copy code
sudo systemctl status sb-watchbot
sudo systemctl status sb-watchbot-levels
