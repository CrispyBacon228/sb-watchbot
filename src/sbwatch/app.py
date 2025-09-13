from __future__ import annotations
import os, logging, json
from typing import Optional
from sbwatch.adapters.logging import setup_logging
from sbwatch.config.settings import settings
from sbwatch.adapters.discord import DiscordSink
from sbwatch.adapters.databento import DataBentoSource
from sbwatch.core.levels import build_levels_for_day
from sbwatch.core.engine import decide_trade_example

log = logging.getLogger("sbwatch.app")

def _sink(verbose: bool=False) -> DiscordSink:
    wh = os.getenv("DISCORD_WEBHOOK_URL") or settings.DISCORD_WEBHOOK_URL
    return DiscordSink(wh, verbose=verbose)

def _source() -> DataBentoSource:
    return DataBentoSource(settings.DATABENTO_API_KEY, settings.DB_DATASET, settings.DB_SCHEMA, settings.FRONT_SYMBOL)

def build_levels(date: Optional[str]=None) -> None:
    setup_logging()
    d = date or "today"
    levels = build_levels_for_day(d)
    log.info("built levels %s", json.dumps(levels))
    os.makedirs("data", exist_ok=True)
    with open("data/levels.json","w") as f: json.dump(levels,f,indent=2)

def run_replay(date: str, verbose: bool=False) -> None:
    setup_logging()
    src = _source()
    sink = _sink(verbose)
    log.info("replay start date=%s dataset=%s schema=%s symbol=%s", date, settings.DB_DATASET, settings.DB_SCHEMA, settings.FRONT_SYMBOL)
    trade = decide_trade_example()
    if trade:
        sink.publish({"content": f"✅ Replay demo: {trade.side} entry {trade.entry} stop {trade.stop} basis {trade.basis}"})
    log.info("replay done")

def run_live(verbose: bool=False) -> None:
    setup_logging()
    src = _source()
    sink = _sink(verbose)
    log.info("live start dataset=%s schema=%s symbol=%s", settings.DB_DATASET, settings.DB_SCHEMA, settings.FRONT_SYMBOL)
    sink.publish({"content":"🟢 sbwatch live started"})
