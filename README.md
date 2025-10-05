🕙 ICT Silver Bullet (10:00–11:00 NY) — Implementation
📘 Replay Mode

The bot enforces these rules during replays:

Time Gate: 10:00–11:00 America/New_York only

Liquidity Sweep:

Bullish: Displacement bar must sweep recent lows within the last SWEEP_LOOKBACK bars

Bearish: Displacement bar must sweep recent highs within the last SWEEP_LOOKBACK bars

Displacement + FVG: 3-bar FVG with minimum displacement (MIN_DISP_PTS) and minimum gap height (MIN_ZONE_PTS)

Entry: Default at the 50% (mean threshold) of the FVG (ENTRY_MODE=mean)

Stop Loss: Beyond the swept swing ± STOP_BUF_TICKS * TICK (ICT-style)

Targets: 1R and 2R, calculated from the SL anchor. Trades with R < MIN_R_POINTS are skipped

Freshness: FVG must be touched within FRESH_MAX_BARS of its creation

All key tunables can be found in:
src/sbwatch/app/replay_alerts.py

⚡ Live Mode

The live runner mirrors replay logic and operates hands-off using systemd services.

Live components:

Fetcher: scripts/live_fetch_nq.sh — keeps live/nq_1m.csv updated (1-minute OHLCV data)

Strategy: src/sbwatch/app/live_sb.py — monitors live data, enforces the 10–11 ET session, detects sweeps + FVGs, and sends alerts

Stops/Targets:

SL = true sweep extreme ± STOP_BUF_TICKS * TICK

TP1 / TP2 = 1R / 2R multiples

⚙️ Services (templates in systemd/)
Service	Description
sb-live-fetch.service	Continuously updates live/nq_1m.csv (1m OHLCV data feed)
sb-live.service	Runs the ICT Silver Bullet strategy and posts alerts (10:00–11:00 ET)
sb-replay-post.timer	Triggers at 11:10 ET daily to run replay and post summary

Environment variables are stored in /etc/sb-watchbot/env, which includes:

DISCORD_WEBHOOK=...
DATABENTO_API_KEY=...
SYM=NQZ5


(Do not share this file or its contents — it contains sensitive credentials.)

🧩 Installation & Startup
# 1. Clone repository
git clone https://github.com/your-username/sb-watchbot.git
cd sb-watchbot

# 2. Create & activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Copy systemd services
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# 5. Enable + start
sudo systemctl enable sb-live-fetch.service sb-live.service sb-replay-post.timer
sudo systemctl start sb-live-fetch.service sb-live.service sb-replay-post.timer

🧪 Testing & Debug

Bypass clock gate (manual run):

python -m sbwatch.app.live_sb --csv live/nq_1m.csv --ignore-clock --heartbeat --daily-pings


Inspect replay outputs:

python scripts/levels_debug.py out/replay_YYYY-MM-DD.csv
python scripts/fvg_debug.py out/replay_YYYY-MM-DD.csv

✅ Summary

When all services are enabled and running, the bot:

Pulls 1-minute NQ data automatically

Executes the Silver Bullet logic between 10:00–11:00 ET

Posts live alerts and a daily replay summary to Discord
