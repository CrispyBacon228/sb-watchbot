from __future__ import annotations
import os, logging, json, yaml, datetime as dt
from zoneinfo import ZoneInfo
from typing import Optional, Iterable
from sbwatch.adapters.logging import setup_logging
from sbwatch.config.settings import settings
from sbwatch.adapters.discord import DiscordSink
from sbwatch.adapters.csvsource import find_csv_for_date, iter_bars_csv
from sbwatch.adapters.databento import DataBentoSource
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

def _am_window_iso(date: str, tz: str) -> tuple[str, str]:
    z = ZoneInfo(tz)
    start = dt.datetime.fromisoformat(f"{date}T10:00:00").replace(tzinfo=z)
    end   = dt.datetime.fromisoformat(f"{date}T11:00:00").replace(tzinfo=z)
    return start.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00","Z"), \
           end.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00","Z")

def build_levels(date: Optional[str]=None) -> None:
    setup_logging()
    d = date or "today"
    levels = {"date": d, "pdh": None, "pdl": None}
    os.makedirs("data", exist_ok=True)
    with open("data/levels.json","w") as f: json.dump(levels,f,indent=2)
    log.info("built levels %s", json.dumps(levels))

def _iter_bars_for_date(date: str, params: SBParams) -> Iterable[dict]:
    # Prefer Databento if key is present; else CSV
    if os.getenv("DATABENTO_API_KEY") or settings.DATABENTO_API_KEY:
        dbs = DataBentoSource(settings.DATABENTO_API_KEY, settings.DB_DATASET, settings.DB_SCHEMA, settings.FRONT_SYMBOL)
        start_iso, end_iso = _am_window_iso(date, params.tz)
        log.info("replay: Databento %s %s %s start=%s end=%s",
                 settings.DB_DATASET, settings.DB_SCHEMA, settings.FRONT_SYMBOL, start_iso, end_iso)
        return dbs.replay(start=start_iso, end=end_iso)
    path = find_csv_for_date(date)
    if not path:
        raise SystemExit(f"no CSV found for {date} (put data/{date}.csv or NQ-{date}-1m.csv)")
    log.info("replay: reading %s", path)
    return iter_bars_csv(path)

def run_replay(date: str, verbose: bool=False) -> None:
    setup_logging()
    sink = _sink(verbose)
    params = _params_from_yaml()
    eng = SBEngine(params)

    pdh = pdl = None
    if os.path.exists("data/levels.json"):
        with open("data/levels.json") as f:
            lv = json.load(f); pdh, pdl = lv.get("pdh"), lv.get("pdl")

    alerts = 0
    for row in _iter_bars_for_date(date, params):
        bar = Bar(**row)
        a = eng.on_bar(bar, pdh=pdh, pdl=pdl)
        if a:
            sink.publish({"content": format_discord(a)})
            alerts += 1
    log.info("replay: done, alerts=%d", alerts)

def run_live(verbose: bool=False) -> None:
    setup_logging()
    sink = _sink(verbose)
    params = _params_from_yaml()
    eng = SBEngine(params)
    if not (os.getenv("DATABENTO_API_KEY") or settings.DATABENTO_API_KEY):
        sink.publish({"content":"🟢 sbwatch live started (Databento key missing; CSV has no live)"}); return
    dbs = DataBentoSource(settings.DATABENTO_API_KEY, settings.DB_DATASET, settings.DB_SCHEMA, settings.FRONT_SYMBOL)
    sink.publish({"content":"🟢 sbwatch live started (Databento)"}); alerts = 0
    for row in dbs.stream():
        bar = Bar(**row)
        a = eng.on_bar(bar)
        if a:
            sink.publish({"content": format_discord(a)})
            alerts += 1
