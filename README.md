SB Simple — Live Alerts & CSV Probes

SB Simple is a lean, production-oriented implementation of the “Silver Bullet” intraday strategy for NQ futures with:

Live alerts (systemd service) delivered to Discord via a webhook

Deterministic level building (Asia, London, PDH/PDL, 10:00–10:59 ET “box”)

CSV probes that replay the day from disk to explain, gate, and deep-trace entries

A small, readable strategy engine (src/sbwatch/strategy.py) that runs on 1-minute bars

This README documents every command in bin/ and probes/, explains how the strategy works, shows alert shapes, and gives ops runbooks and troubleshooting for the current codebase.

Contents

Repo Layout

Quick Start

Environment & Secrets

Daily Levels (auto & manual)

CSV Pull Helpers

Probes (Gate / Explain / DeepTrace / Capture)

Strategy: Rules, Windows, and Entries

Alert Formats (Discord)

Live Service (systemd)

Operational Checks

Troubleshooting

Appendix A — Command Reference (bin/ & probes/)

Appendix B — Levels JSON Schema

Repo Layout
/opt/sb-simple
├── .env                          # local dev/test env (loaded by scripts)
├── bin/
│   ├── build_levels_for_date.py  # build levels.json for a specific date
│   ├── build-levels.sh           # oneshot builder (used by systemd service)
│   └── pull-csv.sh               # helper: pull OHLCV 1m to CSV for a window
├── data/
│   ├── levels/                   # daily levels.json by date
│   ├── csv/                      # historical CSV pulls
│   └── traces/                   # probe outputs
├── probes/
│   ├── alert_equivalence_check.py
│   ├── strategy_capture_csv.py   # pulls + captures a window to CSV
│   ├── strategy_deeptrace_csv.py # verbose trace of decision flow
│   ├── strategy_explain_csv.py   # “engine-like” replay -> entries to CSV
│   └── strategy_gate_csv.py      # debug visibility of gates/filters
├── run_live.py                   # starts the live strategy engine
└── src/sbwatch/
    ├── strategy.py               # SBEngine + notify integration
    ├── notify.py                 # Discord webhook integration
    └── tools/pull_csv.py         # Databento pull helper (uses stype_in='native')


Systemd unit files (on the host):

/etc/systemd/system/sb-live.service      # live alerts
/etc/systemd/system/sb-live.timer        # (optional) if you want to schedule start
/etc/systemd/system/sb-levels.service    # oneshot builder for levels.json
/etc/sb-watchbot.env                     # production env for systemd

Quick Start
# 0) enter the project & venv
cd /opt/sb-simple
. .venv/bin/activate
export PYTHONPATH=src

# 1) verify secrets (masked)
grep -E '^(DB_API_KEY|DATABENTO_API_KEY|DISCORD_WEBHOOK)=' .env /etc/sb-watchbot.env | sed 's/=.*$/=***REDACTED***/'

# 2) build today’s levels (auto usually runs; this is manual)
bash bin/build-levels.sh

# 3) start live alerts
sudo systemctl restart sb-live.service
journalctl -u sb-live.service -n 50 --no-pager

# 4) (optional) run an explain probe for a past day
CSV_DATE=2025-10-24 \
CSV_START=10:00 CSV_END=11:00 \
CSV_OUT="data/csv/2025-10-24_NQZ5_1m.csv" \
bash bin/pull-csv.sh

python probes/strategy_explain_csv.py \
  "data/levels/2025-10-24/levels.json" \
  "data/traces/2025-10-24-explain.csv"

Environment & Secrets

Keep both variables in both files (systemd does not expand ${VAR}):

.env (dev/local)

/etc/sb-watchbot.env (live via systemd)

Required:

Variable	What it does	Example
DB_API_KEY	Databento API key	db-xxxxxxxx...
DATABENTO_API_KEY	Same value as DB_API_KEY (for compat)	db-xxxxxxxx...
DISCORD_WEBHOOK	Discord channel webhook URL	https://discord.com/api/...
SYMBOL/SB_SYMBOL	Contract symbol (native stype)	NQZ5
DATASET	Databento dataset	GLBX.MDP3
SCHEMA	Pull schema	ohlcv-1m

Strategy switches (examples):

USE_PDH_PDL_AS_SWEEP=1
USE_ASIA_AS_SWEEP=1
USE_LONDON_AS_SWEEP=1
USE_BOX=1
SB_WINDOW_START=10:00    # ET
SB_WINDOW_END=11:00      # ET
MAX_LOOKBACK_MIN=90


We set the CSV helpers and pull tools to use stype_in='native' for specific contracts (e.g., NQZ5). If you ever request a continuous symbol, use Databento’s continuous format (NQ.[ROLL].[RANK]) and adjust accordingly.

Daily Levels (auto & manual)
What are “levels” here?

BOX: the 10:00–10:59 ET range (high/low), entry window ends at 11:00 ET.

ASIA: Asia session high/low.

LONDON: London session high/low.

PDH / PDL: prior day’s high/low.

Symbol, dataset, schema metadata.

Levels are written to: data/levels/YYYY-MM-DD/levels.json

Example (truncated):

{
  "date": "2025-10-24",
  "box":   { "high": 25548.75, "low": 25420.75, "start": "10:00", "end": "12:00" },
  "pdh":   25828.0,
  "pdl":   24999.0,
  "asia":  { "high": 25330.0, "low": 25284.75 },
  "london":{ "high": 25381.5, "low": 25324.0 },
  "symbol":"NQZ5",
  "dataset":"GLBX.MDP3",
  "schema":"ohlcv-1m"
}

Auto (systemd oneshot)
sudo systemctl start sb-levels.service
journalctl -u sb-levels.service -n 50 --no-pager


The unit calls:

/opt/sb-simple/bin/build-levels.sh

Manual (specific date)
cd /opt/sb-simple
. .venv/bin/activate
export PYTHONPATH=src

python bin/build_levels_for_date.py 2025-10-24 09:00 12:00
# → writes data/levels/2025-10-24/levels.json

CSV Pull Helpers

Two paths exist:

Unified shell (bin/pull-csv.sh), which reads:

CSV_DATE, CSV_START, CSV_END

CSV_OUT (full path)

SB_SYMBOL/SYMBOL (e.g., NQZ5)

DATABENTO_API_KEY or DB_API_KEY

Python helper (src/sbwatch/tools/pull_csv.py) using stype_in='native'.

Example:

cd /opt/sb-simple
. .venv/bin/activate

export CSV_DATE=2025-10-24
export CSV_START=10:00
export CSV_END=11:00
export CSV_OUT="data/csv/${CSV_DATE}_${SB_SYMBOL}_1m.csv"

bash bin/pull-csv.sh
ls -lh "$CSV_OUT"


If you ever see symbology_invalid_symbol, confirm you are passing a native contract (e.g., NQZ5) and not a continuous alias.

Probes (Gate / Explain / DeepTrace / Capture)

All probes assume:

PYTHONPATH=src

LEVELS JSON available (data/levels/YYYY-MM-DD/levels.json)

Optional CSV prepared in data/csv/… if the script expects one

1) probes/strategy_gate_csv.py

Purpose: shows “gates” (filters) and visibility signals within the entry window.

Usage:

cd /opt/sb-simple
. .venv/bin/activate
export PYTHONPATH=src

python probes/strategy_gate_csv.py \
  "data/csv/2025-10-24_NQZ5_1m.csv" \
  "data/levels/2025-10-24/levels.json" \
  "data/traces/2025-10-24-gate.csv"


Output: CSV with rows for each minute indicating filter states, e.g.,

in_window

swept_box_hi/lo, swept_asia_hi/lo, swept_london_hi/lo, swept_pdh/pdl

other booleans used by the entry logic

2) probes/strategy_explain_csv.py

Purpose: replay day “engine-like” and emit candidate entries and the decisions (accept/reject), useful for validating what live would have done.

Usage:

python probes/strategy_explain_csv.py \
  "data/levels/2025-10-24/levels.json" \
  "data/traces/2025-10-24-explain.csv"


Notes:

If the script expects only LEVELS, it will internally pull or open the default CSV path (depending on your exact code).

If it supports an explicit CSV arg, pass it before LEVELS.

Output fields (typical):

ts (ms)

bar_open, bar_high, bar_low, bar_close, vol

side (SHORT/LONG)

reason / gate (why the candidate qualified)

entry_price, sl, tp, sweep_label

3) probes/strategy_deeptrace_csv.py

Purpose: very verbose signal flow (minute-by-minute), including gate changes and sweep detections. Use this when the “Explain” probe shows a surprising decision and you need deeper context.

Usage:

python probes/strategy_deeptrace_csv.py \
  "data/levels/2025-10-24/levels.json" \
  "data/traces/2025-10-24-deeptrace.csv"

4) probes/strategy_capture_csv.py

Purpose: convenience wrapper to pull the day/window and save a capture CSV in one go.

Usage:

python probes/strategy_capture_csv.py \
  --csv  "data/csv/2025-10-27_NQZ5_1m.csv" \
  --levels "data/levels/2025-10-27/levels.json"

5) probes/alert_equivalence_check.py

Purpose: QA guard — can compare “explain” probe candidates with live alert shapes to ensure parity after code changes.

Usage (typical):

python probes/alert_equivalence_check.py \
  "data/traces/2025-10-24-explain.csv" \
  "data/traces/2025-10-24-gate.csv"

Strategy: Rules, Windows, and Entries

The engine (src/sbwatch/strategy.py) implements a pragmatic “Silver Bullet” variant on 1-minute bars:

Time window (ET): default 10:00–11:00 (configurable via SB_WINDOW_START/END).

Reference levels:

BOX high/low = range of 10:00–10:59

ASIA high/low

LONDON high/low

PDH/PDL

Sweep logic: depending on env switches, a liquidity sweep of one or more levels (BOX/ASIA/LONDON/PDH/PDL) is required before an entry.

Entry direction:

A sweep of highs (BOX high / session highs / PDH) biases SHORT.

A sweep of lows (BOX low / session lows / PDL) biases LONG.

Risk params: entry = last/close at signal minute; sl defaulted or drawn from extra['sl']; optional tp from extra['tp'] if present.

Notifications: When a candidate passes gating rules, we call notify.post_entry(...).

Notify API (current code)

This is important. The code currently calls:

notify.post_entry(
    side: str,             # 'LONG' or 'SHORT'
    entry: float,          # entry price
    sl: float,             # stop loss
    tp: Optional[float],   # take profit or None
    sweep_label: str,      # label text (e.g., 'BOX', 'ASIA', 'LONDON', 'PDH/PDL')
    when: int              # epoch millis
)


This is the mapping we fixed. Do not pass price= or ts= to post_entry in the current repository.

Alert Formats (Discord)

The notify module posts a compact embed/message similar to:

[SB] SHORT 25750.25
• when: 2025-10-27 10:34:00 ET
• sweep: BOX
• sl: 25780.00 | tp: —
• symbol: NQZ5


Field meanings:

Header: [SB] SIDE ENTRY_PRICE

when: signal time (local ET)

sweep: which level blew out (e.g., BOX, ASIA, LONDON, PDH, PDL)

sl/tp: risk parameters if provided

symbol: native contract (e.g., NQZ5)

If you see raw webhook “403 Forbidden”, the webhook is invalid/revoked or lacks channel permission — regenerate it in Discord and update both .env and /etc/sb-watchbot.env.

Live Service (systemd)

Service files:

/etc/systemd/system/sb-live.service → calls run_live.py

/etc/systemd/system/sb-levels.service → runs bin/build-levels.sh (oneshot)

Basic ops:

sudo systemctl daemon-reload

# live alerts
sudo systemctl restart sb-live.service
journalctl -u sb-live.service -n 100 --no-pager

# daily levels
sudo systemctl start sb-levels.service
journalctl -u sb-levels.service -n 50 --no-pager

# enable at boot (optional)
sudo systemctl enable sb-live.service

Operational Checks

1) Environment sanity (masked):

grep -E '^(DB_API_KEY|DATABENTO_API_KEY|DISCORD_WEBHOOK)=' .env /etc/sb-watchbot.env | sed 's/=.*$/=***REDACTED***/'


2) Levels present:

jq . data/levels/$(date +%F)/levels.json | head


3) Service healthy:

journalctl -u sb-live.service -n 120 --no-pager


4) Direct notify self-test:

python - <<'PY'
import time
import sbwatch.notify as n
n.post_entry(side="SHORT", entry=25750.25, sl=0.0, tp=None,
             sweep_label="SELFTEST", when=int(time.time()*1000))
print("sent")
PY


5) Probe “explain” on a known day:

python probes/strategy_explain_csv.py \
  "data/levels/2025-10-24/levels.json" \
  "data/traces/2025-10-24-explain.csv"

Troubleshooting

Databento 400 symbology_invalid_symbol

You passed a continuous symbol format to a native request.

For specific contracts use native (e.g., NQZ5) — our pull uses stype_in='native'.

If you need continuous, use NQ.[ROLL_RULE].[RANK] per Databento docs.

ERROR: DATABENTO_API_KEY not set

Ensure both DB_API_KEY and DATABENTO_API_KEY exist in both .env and /etc/sb-watchbot.env.

Discord HTTPError 403: Forbidden

Webhook is revoked/invalid or missing permission. Create a fresh webhook in the target channel and update both env files; then sudo systemctl restart sb-live.service.

post_entry() got unexpected keyword ...

Your notify API does not accept price/ts. We already mapped to the current signature:
post_entry(side, entry, sl, tp, sweep_label, when)

expected column ts_event missing from returned data (pull)

Mismatch in schema/columns when reading the returned table; ensure SCHEMA=ohlcv-1m and current Databento lib. Re-pull.

Weekend / no data for time range

If your CSV_DATE/CSV_START/CSV_END range falls entirely on a weekend, Databento returns empty. Choose a weekday or adjust the window.

Appendix A — Command Reference (bin/ & probes/)
bin/build-levels.sh

Oneshot builder for “today” used by systemd.

Usage: bash bin/build-levels.sh
Reads: /etc/sb-watchbot.env and ./.env
Writes: data/levels/$(date +%F)/levels.json

bin/build_levels_for_date.py

Build levels for a specific date and time window.

Usage: python bin/build_levels_for_date.py YYYY-MM-DD START_ET END_ET
Example:
  python bin/build_levels_for_date.py 2025-10-24 09:00 12:00

bin/pull-csv.sh

Pull a 1-minute OHLCV CSV via Databento (native contract).

Env:
  CSV_DATE=YYYY-MM-DD
  CSV_START=HH:MM
  CSV_END=HH:MM
  CSV_OUT=path/to/file.csv
  SB_SYMBOL / SYMBOL (e.g., NQZ5)
  DATABENTO_API_KEY / DB_API_KEY
Usage:
  bash bin/pull-csv.sh

probes/strategy_gate_csv.py
Usage:
  python probes/strategy_gate_csv.py <CSV> <LEVELS_JSON> [OUT_CSV]

probes/strategy_explain_csv.py
Usage:
  python probes/strategy_explain_csv.py <LEVELS_JSON> [OUT_CSV]
# Some builds also accept: <CSV> <LEVELS_JSON> [OUT_CSV]

probes/strategy_deeptrace_csv.py
Usage:
  python probes/strategy_deeptrace_csv.py <LEVELS_JSON> [OUT_CSV]

probes/strategy_capture_csv.py
Usage:
  python probes/strategy_capture_csv.py --csv <CSV_PATH> --levels <LEVELS_JSON>

probes/alert_equivalence_check.py
Usage:
  python probes/alert_equivalence_check.py <EXPLAIN_CSV> <GATE_CSV>

Appendix B — Levels JSON Schema
{
  "date": "YYYY-MM-DD",
  "box": {
    "high": <float>,
    "low": <float>,
    "start": "10:00",
    "end": "11:00"
  },
  "pdh": <float>,
  "pdl": <float>,
  "asia":   { "high": <float>, "low": <float> },
  "london": { "high": <float>, "low": <float> },
  "symbol":  "NQZ5",
  "dataset": "GLBX.MDP3",
  "schema":  "ohlcv-1m"
}

Final Notes

Notify API is set to post_entry(side, entry, sl, tp, sweep_label, when) — all live/engine and probes reflect that mapping.

Pull helpers use stype_in='native' for NQZ5 (or whichever specific contract you trade).

The systemd oneshot builder for levels is the source of truth for the day’s reference levels used by both live and probes.
