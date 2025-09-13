from __future__ import annotations
import os, logging, json, yaml  # type: ignore
from typing import Optional
from sbwatch.adapters.logging import setup_logging
from sbwatch.config.settings import settings
from sbwatch.adapters.discord import DiscordSink
from sbwatch.adapters.csvsource import find_csv_for_date, iter_bars_csv
from sbwatch.core.alerts import format_discord
from sbwatch.core.engine import SBEngine, SBParams, Bar

log = logging.getLogger("sbwatch.app")

def _sink(verbose: bool=False) -> DiscordSink:
    wh = os.getenv("DISCORD_WEBHOOK_URL") or settings.DISCORD_WEBHOOK_URL
    return DiscordSink(wh, verbose=verbose)

def _params_from_yaml() -> SBParams:
    with open("configs/settings.yaml","r") as f:
        cfg = yaml.safe_load(f)
    t = cfg["tolerances"]; s = cfg["sessions"]; r = cfg["risk"]; ref = cfg["references"]
    return SBParams(
        tz=s["tz"],
        kill_start=s["ny_killzone_start"],
        kill_end=s["ny_killzone_end"],
        sweep_ticks=t["sweep_ticks"],
        disp_min_ticks=t["displacement_min_ticks"],
        fvg_min_ticks=t["fvg_min_ticks"],
        refill_tol_ticks=t["refill_tolerance_ticks"],
        tp1_r=r["tp1_r_multiple"],
        tp2_r=r["tp2_r_multiple"],
        stop_buf_ticks=r["stop_buffer_ticks"],
        ref_lookback_minutes=ref["ref_lookback_minutes"],
        require_fvg=ref["require_fvg"],
    )

def build_levels(date: Optional[str]=None) -> None:
    setup_logging()
    d = date or "today"
    levels = {"date": d, "pdh": None, "pdl": None}
    os.makedirs("data", exist_ok=True)
    with open("data/levels.json","w") as f: json.dump(levels,f,indent=2)
    log.info("built levels %s", json.dumps(levels))

def run_replay(date: str, verbose: bool=False) -> None:
    setup_logging()
    sink = _sink(verbose)
    params = _params_from_yaml()
    eng = SBEngine(params)

    path = find_csv_for_date(date)
    if not path:
        log.error("no CSV found for date %s (put data/%s.csv or NQ-%s-1m.csv)", date, date, date)
        raise SystemExit(1)
    log.info("replay: reading %s", path)

    pdh = pdl = None
    lvl_path = "data/levels.json"
    if os.path.exists(lvl_path):
        with open(lvl_path) as f:
            lv = json.load(f); pdh, pdl = lv.get("pdh"), lv.get("pdl")

    alerts = 0
    for row in iter_bars_csv(path):
        bar = Bar(**row)
        a = eng.on_bar(bar, pdh=pdh, pdl=pdl)
        if a:
            sink.publish({"content": format_discord(a)})
            alerts += 1
    log.info("replay: done, alerts=%d", alerts)

def run_live(verbose: bool=False) -> None:
    setup_logging()
    sink = _sink(verbose)
    sink.publish({"content":"🟢 sbwatch live started (wire Databento stream next)"})
