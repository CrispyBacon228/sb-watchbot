from __future__ import annotations
import os, logging, json
from typing import Optional
from sbwatch.adapters.logging import setup_logging
from sbwatch.config.settings import settings
from sbwatch.adapters.discord import DiscordSink
from sbwatch.adapters.databento import DataBentoSource   # still a stub; not used yet
from sbwatch.adapters.csvsource import find_csv_for_date, iter_bars_csv
from sbwatch.core.levels import build_levels_for_day
from sbwatch.core.engine import decide_trade_on_bar, Bar
from sbwatch.core.alerts import format_discord

log = logging.getLogger("sbwatch.app")

def _sink(verbose: bool=False) -> DiscordSink:
    wh = os.getenv("DISCORD_WEBHOOK_URL") or settings.DISCORD_WEBHOOK_URL
    return DiscordSink(wh, verbose=verbose)

def _source() -> DataBentoSource:
    # placeholder: we keep signature stable for when you switch to Databento
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
    sink = _sink(verbose)
    path = find_csv_for_date(date)
    if not path:
        log.error("no CSV found for date %s (put data/%s.csv or NQ-%s-1m.csv)", date, date, date)
        raise SystemExit(1)
    log.info("replay: reading %s", path)

    alerts = 0
    for row in iter_bars_csv(path):
        bar = Bar(**row)
        alert = decide_trade_on_bar(bar)
        if alert:
            sink.publish({"content": format_discord(alert)})
            alerts += 1
    log.info("replay: done, alerts=%d", alerts)

def run_live(verbose: bool=False) -> None:
    setup_logging()
    sink = _sink(verbose)
    # When you implement DataBento live streaming, emit from that loop.
    sink.publish({"content":"🟢 sbwatch live started"})
