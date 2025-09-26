from __future__ import annotations
import typer, csv, os
from pathlib import Path
from datetime import datetime, timedelta, timezone, time as dtime
from zoneinfo import ZoneInfo
from sbwatch.strategy.ict import ICTDetector
from sbwatch.util.gate import GateSim
from sbwatch.adapters.databento import ohlcv_range, clamp_end

app = typer.Typer(help="ICT backtest / replay")

TZ_ET = ZoneInfo("America/New_York")

def _rows_for_et_date(symbol: str, dataset: str, schema: str, et_date: str):
    y,m,d = map(int, et_date.split("-"))
    s_et = datetime(y,m,d,0,0,tzinfo=TZ_ET)
    e_et = s_et + timedelta(days=1)
    s_utc = s_et.astimezone(timezone.utc); e_utc = clamp_end(e_et.astimezone(timezone.utc))
    return list(ohlcv_range(dataset, schema, symbol, s_utc, e_utc))

def _in_window(ts_utc: datetime, t0: dtime|None, t1: dtime|None) -> bool:
    if not (t0 and t1): return True
    t_et = ts_utc.astimezone(TZ_ET).time()
    return (t0 <= t_et <= t1)

@app.command("replay")
def replay(
    date: str = typer.Option(..., "--date", "-d", help="ET date YYYY-MM-DD"),
    out: str = typer.Option("./out", "--out", help="Output dir"),
    debug: bool = typer.Option(False, "--debug", help="Print debug counts"),
    et_start: str = typer.Option("10:00", "--et-start", help="ET window start HH:MM"),
    et_end:   str = typer.Option("11:00", "--et-end",   help="ET window end HH:MM"),
):
    dataset = os.getenv("DB_DATASET","GLBX.MDP3")
    schema  = os.getenv("DB_SCHEMA","ohlcv-1m")
    symbol  = os.getenv("FRONT_SYMBOL","NQ?")
    div     = int(os.getenv("PRICE_DIVISOR","1000000000"))
    Path(out).mkdir(parents=True, exist_ok=True)
    out_path = Path(out)/f"ict_{date}.csv"

    t0 = datetime.strptime(et_start, "%H:%M").time() if et_start else None
    t1 = datetime.strptime(et_end,   "%H:%M").time() if et_end   else None

    ict = ICTDetector()
    gate = GateSim()
    rows = _rows_for_et_date(symbol, dataset, schema, date)

    sweeps = fvgs = entries = 0
    with out_path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["ts_utc","side","entry","stop","tp1","tp2","context"])
        for r in rows:
            ts_attr = getattr(r,"ts_event", None) or getattr(r,"ts_recv", None)
            ts = datetime.fromtimestamp(float(ts_attr)/1e9, tz=timezone.utc) if ts_attr else datetime.now(timezone.utc)
            o = float(getattr(r,"open",getattr(r,"o",0.0)))/div
            h = float(getattr(r,"high",getattr(r,"h",0.0)))/div
            l = float(getattr(r,"low", getattrib:=getattr(r,"l",0.0)))/div
            l = float(getattr(r,"low",getattr(r,"l",0.0)))/div
            c = float(getattr(r,"close",getattr(r,"c",0.0)))/div
            before_f, before_s = ict.stats_fvgs, ict.stats_sweeps
            sigs = ict.add_bar(ts,o,h,l,c)
            fvgs   += max(0, ict.stats_fvgs   - before_f)
            sweeps += max(0, ict.stats_sweeps - before_s)
            for s in sigs:
                if _in_window(ts, t0, t1):
                    if not gate.allow_at(ts.timestamp(), s.side, s.entry, getattr(s, 'sweep_id', None)):
                        continue
                    entries += 1
                    w.writerow([ts.isoformat(), s.side, f"{s.entry:.2f}", f"{s.stop:.2f}", f"{s.tp1:.2f}", f"{s.tp2:.2f}", s.context])
    if debug:
        print(f"[ICT DEBUG] {date}  sweeps={sweeps}  fvgs={fvgs}  entries={entries}")
    typer.echo(f"Wrote → {out_path}")
