from __future__ import annotations
import argparse, os, sys
from loguru import logger as log
from .config import load_settings
from .log import setup_logging
from .timebox import now_et, is_us_session
from .levels import Levels
from .sweeps import SweepDetector
from .engine import Engine
from .formatters import format_trade, format_info
from .alerts import Discord
from . import feed as livefeed

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--csv", help="ticks CSV: ts_iso,price")
    return ap.parse_args()

def main():
    args = parse_args()
    setup_logging()
    cfg = load_settings()
    log.info("SB Watchbot starting")

    levels = Levels(cfg.levels_path)
    if not levels.get_for_today(now_et()):
        ex = levels.example_today(now_et())
        log.warning("No levels for today. Write /opt/sb-watchbot/data/levels.json"); log.warning(f"Example: {ex}")

    sweeper = SweepDetector(cfg.level_tolerance_ticks, cfg.tick_size, cfg.sweep_cooldown_min)
    engine = Engine(cfg.tick_size, cfg.stop_buffer_ticks, cfg)
    discord = Discord(cfg.discord_webhook)

    if args.dry_run:
        csv_path = args.csv or os.getenv("DRY_RUN_CSV")
        if csv_path and os.path.exists(csv_path): tick_iter = livefeed.dry_run_ticks(csv_path)
        else:
            from random import random
            from datetime import timedelta
            px = 16000.0; ts = now_et()
            def gen():
                nonlocal px, ts
                for _ in range(1200):
                    px += (random()-0.5) * 2.0; ts += timedelta(seconds=1)
                    yield livefeed.Tick(ts=ts, price=px)
            tick_iter = gen()
    else:
        if not cfg.databento_key:
            log.error("No DATABENTO_API_KEY in .env. Use --dry-run until you add it."); sys.exit(1)
        tick_iter = livefeed.live_ticks(cfg.databento_key, cfg.instrument)

    for t in tick_iter:
        engine.on_tick_for_candles(t.ts, t.price)
        if not is_us_session(t.ts.astimezone(now_et().tzinfo)): continue

        today_levels = levels.get_for_today(t.ts)
        if not today_levels: continue

        lvmap = engine.build_levels_map(today_levels)
        evt = sweeper.check(t.ts, t.price, lvmap)
        if not evt: continue

        idea = engine.decide(t.ts, evt.direction, evt.level_name, evt.level_price, t.price)
        if not idea: continue

        if idea.kind in ("SB","TRADE"):
            discord.post(format_trade(idea))
        else:
            bias = "Long Bias" if "LONG" in idea.side else "Short Bias"
            discord.post(format_info(idea.level_name, bias, t.price, t.ts.strftime("%H:%M:%S ET"), tol_ticks=3))

if __name__ == "__main__":
    main()
