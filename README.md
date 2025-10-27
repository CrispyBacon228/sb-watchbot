🟢 SB Watchbot — Official Live ICT Silver Bullet Auto-Alert Engine

NQ Futures · Databento MDP3 · Discord Webhook Notifications

📘 Overview

SB Watchbot is a fully-automated, low-latency alert engine built around the ICT Silver Bullet framework for the Nasdaq E-Mini (NQ) futures market.
It:

Pulls live or historical 1-minute OHLCV bars via Databento MDP3.

Builds structured Asia / London / 10 o’clock Box / PDH / PDL levels each day.

Detects sweeps, qualifies setups, and triggers Discord alerts.

Includes a suite of CSV-based probes for back-testing and debugging.

🧭 Table of Contents

Architecture & Layout

Quick Start

Environment Variables

Daily Level Builder

CSV Pull Helper

Probe Suite

Strategy Logic

Alert Format & Examples

Systemd Live Service

Ops & Health Checks

Troubleshooting

🧩 Architecture & Layout
/opt/sb-simple
├── bin/                     # operational scripts
│   ├── build-levels.sh
│   ├── build_levels_for_date.py
│   └── pull-csv.sh
├── probes/                  # diagnostic replay tools
│   ├── strategy_gate_csv.py
│   ├── strategy_explain_csv.py
│   ├── strategy_deeptrace_csv.py
│   ├── strategy_capture_csv.py
│   └── alert_equivalence_check.py
├── src/sbwatch/
│   ├── strategy.py          # core Silver Bullet logic
│   ├── notify.py            # Discord integration
│   └── tools/pull_csv.py    # Databento interface (stype_in='native')
├── data/
│   ├── levels/              # daily levels.json
│   ├── csv/                 # cached bar data
│   └── traces/              # probe outputs
└── run_live.py              # entry for sb-live.service


System services:

/etc/systemd/system/sb-live.service
/etc/systemd/system/sb-levels.service
/etc/sb-watchbot.env

⚡ Quick Start
cd /opt/sb-simple
. .venv/bin/activate
export PYTHONPATH=src

# build today's reference levels
bash bin/build-levels.sh

# verify or start live engine
sudo systemctl restart sb-live.service
journalctl -u sb-live.service -n 60 --no-pager

🔐 Environment Variables
Variable	Purpose	Example
DB_API_KEY	Databento API key	db-xxxx...
DATABENTO_API_KEY	duplicate for compatibility	same as above
DISCORD_WEBHOOK	target Discord channel	https://discord.com/api/webhooks/...
SYMBOL / SB_SYMBOL	contract symbol	NQZ5
DATASET	Databento dataset	GLBX.MDP3
SCHEMA	bar schema	ohlcv-1m
SB_WINDOW_START	strategy open	10:00
SB_WINDOW_END	strategy close	11:00

Keep identical key values in both .env and /etc/sb-watchbot.env.

🧱 Daily Level Builder
# run manually for any date
python bin/build_levels_for_date.py 2025-10-24 09:00 12:00
# → data/levels/2025-10-24/levels.json


Each JSON includes:

{
  "box": { "high":25548.75, "low":25420.75, "start":"10:00", "end":"11:00" },
  "asia": { "high":25330.0, "low":25284.75 },
  "london": { "high":25381.5, "low":25324.0 },
  "pdh":25828.0,
  "pdl":24999.0
}

🧮 CSV Pull Helper
CSV_DATE=2025-10-27 CSV_START=10:00 CSV_END=11:00 \
CSV_OUT="data/csv/2025-10-27_NQZ5_1m.csv" \
bash bin/pull-csv.sh


Uses pull_csv.py internally with:

client = DBHistorical()  # key read from env
stype_in='native'

🔍 Probe Suite
Probe	Purpose	Output
strategy_gate_csv.py	show gate/filter states each minute	*-gate.csv
strategy_explain_csv.py	replay full engine decisions	*-explain.csv
strategy_deeptrace_csv.py	verbose diagnostic of logic flow	*-deeptrace.csv
strategy_capture_csv.py	auto-pull + capture window	CSV in /data/traces
alert_equivalence_check.py	verify probe/live parity	stdout comparison

Example:

python probes/strategy_explain_csv.py data/levels/2025-10-24/levels.json data/traces/2025-10-24-explain.csv

🧠 Strategy Logic

Framework: ICT Silver Bullet
Time window: 10:00 – 11:00 ET
Concept: after London/Asia liquidity sweeps, NY box break triggers setups.

Core sequence:

Define session ranges (Asia 00–05, London 03–08, Box 10–11 ET).

Detect a sweep of prior liquidity (PDH, PDL, session highs/lows).

Confirm opposite-side displacement candle within window.

Send alert with side, entry, sl, optional tp, sweep_label.

🔔 Alert Format & Examples

Sent by src/sbwatch/notify.py → Discord.

Live Example (SHORT):

[SB] SHORT 25750.25
• when: 2025-10-27 10:34 ET
• sweep: BOX
• sl: 25780.00 | tp: —
• symbol: NQZ5


Signature in code:

notify.post_entry(
    side="SHORT",
    entry=25750.25,
    sl=0.0,
    tp=None,
    sweep_label="BOX",
    when=timestamp_ms
)

🧾 Systemd Live Service
sudo systemctl daemon-reload
sudo systemctl enable sb-live.service
sudo systemctl restart sb-live.service
journalctl -u sb-live.service -n 80 --no-pager


sb-live.service → runs run_live.py

sb-levels.service → builds new levels.json daily

🧰 Ops & Health Checks
# verify env keys (masked)
grep -E '^(DB_API_KEY|DATABENTO_API_KEY|DISCORD_WEBHOOK)=' .env /etc/sb-watchbot.env | sed 's/=.*$/=***REDACTED***/'

# check current levels
jq . data/levels/$(date +%F)/levels.json | head

# view latest alerts / logs
journalctl -u sb-live.service -n 120 --no-pager

# self-test webhook
python - <<'PY'
import time, sbwatch.notify as n
n.post_entry(side="SHORT", entry=25750.25, sl=0.0, tp=None,
             sweep_label="SELFTEST", when=int(time.time()*1000))
print("✅ sent test")
PY

🧩 Troubleshooting
Symptom	Fix
symbology_invalid_symbol	use native contract (NQZ5), not continuous
unexpected keyword 'price'	strategy patched to use entry, when
HTTPError 403 Forbidden	webhook invalid; regenerate in Discord
empty CSV on weekend	Databento has no data for non-sessions
live service crash	journalctl -u sb-live.service → trace
missing env var	confirm in both .env and /etc/sb-watchbot.env
🧮 Appendix A — Commands by File
Script	Command	Description
bin/build-levels.sh	bash bin/build-levels.sh	builds current day’s levels
bin/build_levels_for_date.py	python bin/build_levels_for_date.py YYYY-MM-DD START END	manual date build
bin/pull-csv.sh	see CSV Pull Helper
	fetch OHLCV data
probes/strategy_gate_csv.py	python probes/strategy_gate_csv.py CSV LEVELS OUT	gate map
probes/strategy_explain_csv.py	python probes/strategy_explain_csv.py LEVELS OUT	replay
probes/strategy_deeptrace_csv.py	python probes/strategy_deeptrace_csv.py LEVELS OUT	verbose trace
probes/strategy_capture_csv.py	python probes/strategy_capture_csv.py --csv CSV --levels LEVELS	capture window
probes/alert_equivalence_check.py	compare alert equivalence	parity test
🧾 Appendix B — Levels JSON Schema
{
  "date": "YYYY-MM-DD",
  "box": {"high":0,"low":0,"start":"10:00","end":"11:00"},
  "pdh": 0.0,
  "pdl": 0.0,
  "asia": {"high":0,"low":0},
  "london": {"high":0,"low":0},
  "symbol": "NQZ5",
  "dataset": "GLBX.MDP3",
  "schema": "ohlcv-1m"
}

✅ Final Notes

post_entry(side, entry, sl, tp, sweep_label, when) is the only supported signature — all live and probe paths aligned.

stype_in='native' ensures valid Databento symbol pulls.

Systemd handles daily level generation and live runtime.
