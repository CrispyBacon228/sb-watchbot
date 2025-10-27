SB Watchbot — Official Live ICT Silver Bullet Auto-Alert Engine

NQ Futures · Databento MDP3 · Discord Webhook Notifications

Purpose. SB Watchbot ingests live or historical 1-minute bars, builds daily reference levels (Asia, London, 10:00–11:00 box, PDH/PDL), evaluates ICT Silver Bullet conditions, and posts structured alerts to Discord. A probe suite is included for replay and debugging.

Table of Contents

Architecture

Quick Start

Environment

Level Builder

CSV Pull Helper

Probes

Strategy

Alert Format

Systemd (Live)

Ops & Health

Troubleshooting

Command Reference

Levels JSON Schema

Architecture
/opt/sb-simple
├─ bin/                          # operational scripts
│  ├─ build-levels.sh
│  ├─ build_levels_for_date.py
│  └─ pull-csv.sh
├─ probes/                       # CSV-based replay tools
│  ├─ strategy_gate_csv.py
│  ├─ strategy_explain_csv.py
│  ├─ strategy_deeptrace_csv.py
│  ├─ strategy_capture_csv.py
│  └─ alert_equivalence_check.py
├─ src/sbwatch/
│  ├─ strategy.py                # Silver Bullet engine
│  ├─ notify.py                  # Discord/webhook posting
│  └─ tools/pull_csv.py          # Databento interface (1m OHLCV)
├─ data/
│  ├─ levels/                    # daily levels.json (per date)
│  ├─ csv/                       # cached bar CSVs
│  └─ traces/                    # probe outputs
└─ run_live.py                   # entry point for sb-live.service


System services and env:

/etc/systemd/system/sb-live.service
/etc/systemd/system/sb-levels.service
/etc/sb-watchbot.env

Quick Start
cd /opt/sb-simple
. .venv/bin/activate
export PYTHONPATH=src

# 1) Build today's levels (Asia/London/Box/PDH/PDL)
bash bin/build-levels.sh

# 2) Start or restart live service
sudo systemctl restart sb-live.service
journalctl -u sb-live.service -n 80 --no-pager

Environment

Set variables in both your local .env (for manual runs) and /etc/sb-watchbot.env (for services).

Variable	Description	Example
DB_API_KEY / DATABENTO_API_KEY	Databento API key	db-xxxxx...
DISCORD_WEBHOOK	Discord webhook URL	https://discord.com/api/webhooks/...
SYMBOL or SB_SYMBOL	Trading symbol (native, not continuous)	NQZ5
DATASET	Databento dataset	GLBX.MDP3
SCHEMA	Bar schema	ohlcv-1m
SB_WINDOW_START	Strategy window start (ET)	10:00
SB_WINDOW_END	Strategy window end (ET)	11:00
Session toggles	Optional sweep sources	USE_ASIA_AS_SWEEP=1, USE_LONDON_AS_SWEEP=1, USE_PDH_PDL_AS_SWEEP=1

Tip: Keep keys identical across .env and /etc/sb-watchbot.env.
Symbols: Use native contract (e.g., NQZ5), not continuous (NQ).

Level Builder

Build levels for today (service uses this automatically):

bash bin/build-levels.sh


Build levels for a specific date (repro/debug):

python bin/build_levels_for_date.py 2025-10-24 09:00 12:00
# → data/levels/2025-10-24/levels.json


Levels JSON example:

{
  "date": "2025-10-24",
  "box": {"high":25548.75, "low":25420.75, "start":"10:00", "end":"11:00"},
  "asia": {"high":25330.0, "low":25284.75},
  "london": {"high":25381.5, "low":25324.0},
  "pdh": 25828.0,
  "pdl": 24999.0,
  "symbol": "NQZ5",
  "dataset": "GLBX.MDP3",
  "schema": "ohlcv-1m"
}

CSV Pull Helper

Pull a CSV window from Databento (1m OHLCV):

CSV_DATE=2025-10-27 CSV_START=10:00 CSV_END=11:00 \
CSV_OUT="data/csv/2025-10-27_NQZ5_1m.csv" \
bash bin/pull-csv.sh


Internally uses src/sbwatch/tools/pull_csv.py with stype_in="native" and API key read from environment.

Probes

All probes operate on CSV + levels for reproducible analysis.

Probe	What it does	Output
probes/strategy_gate_csv.py	Minute-by-minute gate/filter states	*-gate.csv
probes/strategy_explain_csv.py	Full decision trace (engine-like)	*-explain.csv
probes/strategy_deeptrace_csv.py	Very verbose diagnostic flow	*-deeptrace.csv
probes/strategy_capture_csv.py	Pulls CSV + captures window	data/traces/*.csv
probes/alert_equivalence_check.py	Probe vs live parity sanity check	stdout

Example (engine replay):

python probes/strategy_explain_csv.py \
  data/levels/2025-10-24/levels.json \
  data/traces/2025-10-24-explain.csv

Strategy

Model. ICT Silver Bullet — New York 10:00–11:00 ET window.

Concept.

Build session ranges: Asia, London, NY Box (10–11), and PDH/PDL.

Detect sweep of prior liquidity (take out Asia/London/PDH/PDL extremes).

Confirm displacement back through the range.

Emit entry with side, entry, sl, optional tp, sweep_label, when.

Inputs.

Levels: data/levels/<date>/levels.json

Bars: live stream (systemd) or CSV (probes)

Core function signatures.

Strategy emits alerts via notify.post_entry(side, entry, sl, tp, sweep_label, when)

Live path runs in run_live.py with src/sbwatch/strategy.py

Alert Format

Discord message produced by src/sbwatch/notify.py.

Short example:

[SB] SHORT 25750.25
when: 2025-10-27 10:34 ET
sweep: BOX
sl: 25780.00
tp: —
symbol: NQZ5


Call site (normalized signature):

notify.post_entry(
  side="SHORT",
  entry=25750.25,
  sl=25780.00,
  tp=None,
  sweep_label="BOX",
  when=timestamp_ms
)


Note: The engine has been normalized to use the keyword args above everywhere (live + probes).

Systemd (Live)

Enable and operate the live service:

sudo systemctl daemon-reload

# live alerts engine
sudo systemctl enable sb-live.service
sudo systemctl restart sb-live.service
journalctl -u sb-live.service -n 120 --no-pager

# daily levels builder (oneshot timer/service pattern if configured)
sudo systemctl enable sb-levels.service
sudo systemctl start sb-levels.service
journalctl -u sb-levels.service -n 80 --no-pager

Ops & Health

Verify masked env:

grep -E '^(DB_API_KEY|DATABENTO_API_KEY|DISCORD_WEBHOOK)=' .env /etc/sb-watchbot.env \
  | sed 's/=.*$/=***REDACTED***/'


Check today’s levels:

jq . data/levels/$(date +%F)/levels.json | head


Logs:

journalctl -u sb-live.service -n 150 --no-pager


Webhook self-test:

python - <<'PY'
import time
from sbwatch import notify
notify.post_entry(
  side="SHORT", entry=25750.25, sl=0.0, tp=None,
  sweep_label="SELFTEST", when=int(time.time()*1000)
)
print("sent")
PY

Troubleshooting
Symptom	Likely cause	Fix
symbology_invalid_symbol	Using continuous (NQ)	Use native (NQZ5) and stype_in="native"
unexpected keyword argument 'price'	Old signature	All call sites use entry/sl/tp/when — pull latest
403 Forbidden on webhook	Bad/expired webhook	Regenerate Discord webhook
CSV empty on weekends	Market closed	Choose a weekday session
Live service exits on start	Syntax/env issues	journalctl -u sb-live.service for full trace
No alerts	Levels missing, env mismatch, gate failed	Confirm levels exist; check env; run a probe with CSV
Command Reference

bin

Script	Usage	Purpose
bin/build-levels.sh	bash bin/build-levels.sh	Build today’s levels
bin/build_levels_for_date.py	python bin/build_levels_for_date.py YYYY-MM-DD 09:00 12:00	Build for specific date
bin/pull-csv.sh	see CSV pull
	Pull CSV bars via Databento

probes

Script	Usage (examples)	Output
strategy_gate_csv.py	python probes/strategy_gate_csv.py CSV LEVELS OUT	*-gate.csv
strategy_explain_csv.py	python probes/strategy_explain_csv.py LEVELS OUT	*-explain.csv
strategy_deeptrace_csv.py	python probes/strategy_deeptrace_csv.py LEVELS OUT	*-deeptrace.csv
strategy_capture_csv.py	python probes/strategy_capture_csv.py --csv CSV --levels LEVELS	CSV in data/traces/
alert_equivalence_check.py	compare probe vs live	stdout
Levels JSON Schema
{
  "date": "YYYY-MM-DD",
  "box": { "high": 0.0, "low": 0.0, "start": "10:00", "end": "11:00" },
  "pdh": 0.0,
  "pdl": 0.0,
  "asia": { "high": 0.0, "low": 0.0 },
  "london": { "high": 0.0, "low": 0.0 },
  "symbol": "NQZ5",
  "dataset": "GLBX.MDP3",
  "schema": "ohlcv-1m"
}

Notes

Uniform notify signature: post_entry(side, entry, sl, tp, sweep_label, when) across live + probes.

Databento: API key required; GLBX.MDP3 + ohlcv-1m + native symbol (NQZ5).

Reliability: systemd manages process lifecycle; daily levels build before NY window.
stype_in='native' ensures valid Databento symbol pulls.

Systemd handles daily level generation and live runtime.
