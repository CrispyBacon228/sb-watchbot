Live market “level watch” bot for futures.
Builds daily session levels (PDH/PDL, Asia, London), watches live 1-minute OHLCV from Databento, and sends Discord alerts when price wicks beyond a level and closes back inside (lower noise than raw crosses). Includes replay-on-a-date to export signals to CSV.

Features

Daily levels builder → ./data/levels.json

Live watcher with:

Wick-reject alerts (PDH/PDL/Asia/London)

Optional crosses (off by default)

Killzone gating (RTH morning + PM by default)

Auto-reload levels when file/date changes

Discord notifications

Per-day CSV logging of alerts → ./out/alerts_live_YYYY-MM-DD.csv

Adaptive backoff for Databento “available_end” lag

Replay a past day (from Databento or your own CSV) → ./out/replay_<DATE>.csv

Simple health status and test helpers (notify test-discord, notify test-log)

Quick Start
# 1) clone + venv
git clone https://github.com/<you>/sb-watchbot.git
cd sb-watchbot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 2) create .env (example)
cat > .env <<'ENV'
DATABENTO_API_KEY=YOUR_KEY
FRONT_SYMBOL=NQZ5
DB_DATASET=GLBX.MDP3
DB_SCHEMA=ohlcv-1m
PRICE_DIVISOR=1000000000
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXXX/XXXXXXXX
# polling / throttles
POLL_SECONDS=5
COOLDOWN_SEC=300
MARGIN_SEC=900
# signals
TICK_SIZE=0.25
TOL_TICKS=4
WICK_ONLY=true
# killzones (ET)
ENABLE_KILLZONE=true
KZ1_START=09:30
KZ1_END=11:00
KZ2_START=13:30
KZ2_END=15:30
# live CSV (rotates by ET date)
ALERTS_LOG_TEMPLATE=./out/alerts_live_%Y-%m-%d.csv
# heartbeat / reloads
LEVELS_RELOAD_SEC=60
HEARTBEAT_MIN=60
ENV

CLI

All commands auto-load .env.

# build levels for a date (ET)
python -m sbwatch.cli.main levels build --date 2025-09-25

# start live watcher (foreground)
python -m sbwatch.cli.main live run

# send a Discord test message
python -m sbwatch.cli.main notify test-discord

# write a dummy row to the live alerts CSV (sanity-check logging)
python -m sbwatch.cli.main notify test-log

# show health snapshot (ET clock, killzones, levels summary, env bits)
python -m sbwatch.cli.main status show
