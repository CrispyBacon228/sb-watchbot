# SB Watchbot (simple)

Discord alert bot for NQ (Databento GLBX.MDP3 ohlcv-1m) implementing a minimal ICT Silver Bullet for the 10:00–11:00 ET window.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill your DB_API_KEY and DISCORD_WEBHOOK
Commands
Build levels (09:00–09:59 box + PDH/PDL + optional Asia/London):

bash
Copy code
./.venv/bin/python sb_bot.py --build-levels
Run live (listens during 10:00–11:00 ET; uses levels.json):

bash
Copy code
./.venv/bin/python sb_bot.py --live
Optional .env flags:

ini
Copy code
INCLUDE_ASIA_LONDON=1
USE_PDH_PDL_AS_SWEEP=1
USE_ASIA_AS_SWEEP=1
USE_LONDON_AS_SWEEP=1
# test outside window:
# LIVE_START=00:00
# LIVE_END=23:59
Systemd (optional)
See systemd/ for sample units:

sb-levels.timer → 09:40 ET daily (Mon–Fri)

sb-live.timer → 09:59:30 ET (Mon–Fri)

Enable:

bash
Copy code
sudo cp systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sb-levels.timer sb-live.timer
Keep .env private. Never commit it—use .env.example in the repo.
