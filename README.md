
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
