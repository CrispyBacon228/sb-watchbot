# 🧠 SB Watchbot — Silver Bullet Automation

SB Watchbot is a full automation suite for running and monitoring the **ICT Silver Bullet strategy** using live and replayed market data from **Databento**.  
It handles:
- 📡 **Live monitoring** (09:30–11:05 ET)  
- 🎞️ **Replay mode** for historical days  
- 🪄 **Automated daily replays + Discord summaries**  
- 🧾 **System audit and health checks**

---

## 📦 Features

| Module | Description |
|---------|--------------|
| `live_sb` | Live ICT Silver Bullet engine (runs in systemd) |
| `replay_day.py` | Replay any trading day using Databento 1-minute bars |
| `replay_and_post.py` | Daily replay + Discord post automation |
| `sb-audit.sh` | Audits all system files, syntax, and live service health |
| `sbwatch.cli.main` | Typer CLI interface for running replays manually |
| `systemd` | Runs and schedules all automation services and timers |

---

## ⚙️ Installation

### 1️⃣ Clone and set up environment
```bash
sudo apt update && sudo apt install -y python3-venv git
git clone https://github.com/CrispyBacon228/sb-watchbot.git /opt/sb-watchbot
cd /opt/sb-watchbot
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
2️⃣ Create your .env
Create /opt/sb-watchbot/.env and include:

bash
Copy code
# Discord webhook (for live + post updates)
DISCORD_WEBHOOK=https://discord.com/api/webhooks/XXXX/YYYY
# Databento credentials
DATABENTO_API_KEY=db-YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
# Timezone
TZ=America/New_York
🔴 Live Mode
The live service runs the Silver Bullet monitor between 09:30–11:05 ET, posts heartbeat and “no trades” updates, and streams 1-minute Databento data.

Run manually
bash
Copy code
python -m sbwatch.app.live_sb --csv live/nq_1m.csv --poll 5 --heartbeat --daily-pings
Managed by systemd
Service: /etc/systemd/system/sb-live.service

ini
Copy code
ExecStart=/bin/bash -c 'source .venv/bin/activate && PYTHONPATH=. \
python -m sbwatch.app.live_sb --csv /opt/sb-watchbot/live/nq_1m.csv \
--poll 5 --heartbeat --daily-pings 2>&1 | tee -a out/live.log'
To check:

bash
Copy code
systemctl status sb-live.service --no-pager
journalctl -u sb-live.service -n 100 --no-pager
🔁 Replay Mode (Manual)
Use the Typer CLI interface to run a replay for any given trading date.

Command
bash
Copy code
python -m sbwatch.cli.main replay run \
  --date "$(TZ=America/New_York date +%F)" \
  --out ./out
Example
Replay October 10, 2025:

bash
Copy code
python -m sbwatch.cli.main replay run --date 2025-10-10 --out ./out
Output: out/replay_2025-10-10.csv

📆 Automated Daily Replay + Discord Summary
Every weekday at 11:10 ET, systemd runs a daily replay for the current date and posts a summary to Discord.

Units
File	Path	Description
sb-replay-post.service	/etc/systemd/system/sb-replay-post.service	Runs the daily replay + post
sb-replay-post.timer	/etc/systemd/system/sb-replay-post.timer	Triggers at 11:10 ET (Mon–Fri)

Service Logic
Runs:

bash
Copy code
source .venv/bin/activate && set -a && . ./.env && set +a && \
python scripts/replay_and_post.py --date "$(TZ=America/New_York date -I)"
The script:

Skips weekends automatically

Runs scripts/replay_day.sh internally

Posts completion or failure to Discord

Manual Test
bash
Copy code
sudo systemctl start sb-replay-post.service
journalctl -u sb-replay-post.service -n 50 --no-pager
📡 Discord Integration
SB Watchbot posts messages like:

yaml
Copy code
✅ SB Watchbot: Replay complete for 2025-10-10 ET
⚠️ SB Watchbot: Replay failed for 2025-10-10 ET (exit 1)
💤 SB Watchbot: Weekend (2025-10-11 ET) — skipping replay/post.
The webhook is defined in .env as DISCORD_WEBHOOK.

🧾 Audit and Diagnostics
Run the full environment audit at any time:

bash
Copy code
bin/sb-audit.sh
Checks:

repo structure

Python + Bash syntax

systemd units

.env keys

live service status

tracked runtime artifacts

Example output:

diff
Copy code
=== BASIC STRUCTURE ===
OK src tree present
OK fetch script present

=== SYSTEMD UNITS IN REPO ===
OK sb-live.service
OK sb-live-fetch.service
⏱ Timer Overview
Timer	Schedule	Action
sb-replay-post.timer	Weekdays 11:10 ET	Run replay + Discord post
sb-live.service	Continuous	Live Silver Bullet alerts
sb-live-fetch.service	Continuous	Databento 1m feed
sb-audit.sh	Manual	Full system verification

List all timers:

bash
Copy code
systemctl list-timers --no-pager
🧹 Weekend Guard
Both replay_day.py and replay_and_post.py skip weekends automatically to prevent Databento 422 errors when no market data exists.

🧰 Useful Commands
Action	Command
Run replay for today	scripts/replay_day.sh --date "$(TZ=America/New_York date +%F)"
Run daily post manually	sudo systemctl start sb-replay-post.service
Check daily post logs	journalctl -u sb-replay-post.service -n 50 --no-pager
Check live logs	journalctl -u sb-live.service -n 100 --no-pager
Run audit	bin/sb-audit.sh

🧠 Notes
.env is never committed (contains private API keys).

All services assume the working directory /opt/sb-watchbot.

Python CLI (sbwatch.cli.main) replaces all legacy sbwatch.app.replay_alerts imports.

Replay window: 09:30 – 11:05 ET (UTC 13:30 – 15:05).

Live and replay CSVs are written to /opt/sb-watchbot/out/.

✅ System Ready Checklist
 Live alerts running via systemd

 Replay verified via CLI

 Daily post timer active

 Weekend guard in place

 Discord webhook confirmed HTTP 200
