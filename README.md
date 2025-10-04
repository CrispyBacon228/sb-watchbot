
## ICT Silver Bullet (10:00–11:00 NY) — Implementation

Rules the bot enforces during replay:
- **Time gate**: 10:00–11:00 America/New_York only.
- **Liquidity sweep required**:
  - Bullish: the displacement bar must **sweep lows** within the last `SWEEP_LOOKBACK` bars.
  - Bearish: the displacement bar must **sweep highs** within the last `SWEEP_LOOKBACK` bars.
- **Displacement + FVG**: 3-bar FVG with `MIN_DISP_PTS` (bar range surrogate) and `MIN_ZONE_PTS` (gap height).
- **Entry**: at the **mean threshold (50%)** of the FVG by default (`ENTRY_MODE=mean`).
- **Stop**: **beyond the swept swing** ± `STOP_BUF_TICKS * TICK` (ICT style).
- **Targets**: 1R and 2R from the stop-anchored R. Trades with `R < MIN_R_POINTS` are skipped.
- **Freshness**: FVG must be touched within `FRESH_MAX_BARS` of creation.

Key tunables live in `src/sbwatch/app/replay_alerts.py`:

## Live Mode

This repo includes a live runner that mirrors the replay logic for ICT Silver Bullet (10–11 ET).

- **Fetcher:** `scripts/live_fetch_nq.sh` keeps `live/nq_1m.csv` updated (Databento, 1-min OHLCV).
- **Strategy:** `src/sbwatch/app/live_sb.py` reads `live/nq_1m.csv`, enforces 10–11 ET, requires a recent sweep, detects 3-bar FVGs, and alerts to Discord.
- **Stops/TPs:** SL = true sweep extreme ± `STOP_BUF_TICKS * TICK`; TP1/TP2 = 1R/2R off that SL.
- **Services:** `sb-live-fetch.service`, `sb-live.service` (systemd).

Env:

## Live Mode (hands-off)

**Services** (templates in `systemd/`):
- `sb-live-fetch.service` — updates `live/nq_1m.csv` (Databento 1m OHLCV)
- `sb-live.service` — runs the ICT SB strategy and posts alerts to Discord (10:00–11:00 ET)
- `sb-replay-post.timer` — at **11:10 ET** runs the day’s replay and posts a summary to Discord

**Env** (in `/etc/sb-watchbot/env`):
DISCORD_WEBHOOK=https://discord.com/api/webhooks/1422365990737412168/8FwBC52I-zs8WZv_ZyFjnTDHgS_Gr0TYFLSaNo9cqhsS620Vv5vsZOsGlRhlZXTlbaVM
DATABENTO_API_KEY=db-qarsfTHECTCLYKcDphtV3Nw6Y7WLi
SYM=NQZ5

**Install & start**:

**Testing**:
- Bypass clock: `python -m sbwatch.app.live_sb --csv live/nq_1m.csv --ignore-clock --heartbeat --daily-pings`
- Debug levels/FVGs: `python scripts/levels_debug.py out/replay_YYYY-MM-DD.csv`, `python scripts/fvg_debug.py out/replay_YYYY-MM-DD.csv`
