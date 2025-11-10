✅ Repo Purpose

This is an algorithmic trading bot for Nasdaq futures (NQ) built to detect ICT Silver Bullet setups and send alerts to Discord in real time using Databento market data.

🧠 Core Architecture
sb-watchbot-main/
│
├── run_live.py          → Main live runner (starts data stream + strategy loop)
├── sb_bot.py            → Discord alert / message sending logic
├── test_strategy_run.py → Local offline test script for strategy
│
├── src/sbwatch/
│   ├── strategy.py      → ICT Silver Bullet logic (sweeps, FVGs, entries, SL, TP)
│   ├── config.py        → Env vars, constants, session times, thresholds
│   ├── data.py          → Reads minute CSV + handles market data objects
│   ├── utils.py         → Helper functions (time, logging, formatting, math)
│   │
│   ├── adapters/
│   │   └── databento.py → Connects to Databento API & streams CME MDP3 market data
│   │
│   ├── stream/
│   │   └── minute_proxy.py → Keeps a "live minute candle" updating every second
│   │                         so strategy doesn't wait for candle close
│   │
│   └── tools/
│        ├── pull_csv.py          → Downloads historical data
│        ├── pull_today_csv.py    → Pulls current day data
│        ├── levels_from_csv.py   → Precomputes intraday levels
│
├── systemd/
│   ├── sb-live.service  → Runs live trading bot as system daemon
│   ├── sb-live.timer    → Starts it on schedule
│   ├── sb-levels.service→ Level builder before session
│   └── sb-levels.timer  → Schedules daily level building
│
└── .env.example         → API keys, Discord webhook, Databento token

🔥 What the bot actually does
1. Market data ingestion
   Connects to Databento CME Globex MDP3 feed (for NQ futures)
	Also maintains a local 1-minute CSV that updates every second (minute_proxy.py)
	→ this allows the strategy to act mid-candle with no delay
2. Strategy execution
   strategy.py watches for:
	ICT Concept	Implemented?
	Liquidity Sweep	✅
	Fair Value Gap (FVG)	✅
	Displacement validation	✅
	Entry + SL + TP calculation	✅
	Contract sizing via tick risk	✅
3. Alerts
   sb_bot.py posts Discord messages like:

	🟢 Bot armed

	🟩 SB Entry (LONG/SHORT)

	⚙️ Risk model + contracts + TP/SL

	⚪ No valid trade
4. Automation
   Systemd timers automatically run:
   	Pre-market levels calculation
	Market open strategy execution
	(Optional) replay testing after market hours

🚀 Expected Live Flow
Databento live tick feed
        ↓
minute_proxy.py builds 1m candle (updates every second)
        ↓
strategy.py checks sweeps/FVG mid-candle
        ↓
Valid setup found
        ↓
sb_bot.py sends Discord alert instantly (no 1m delay)
