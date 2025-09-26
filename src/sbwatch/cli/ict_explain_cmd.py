from __future__ import annotations
import typer, os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sbwatch.strategy.ict import ICTDetector
from sbwatch.adapters.databento import ohlcv_range, clamp_end

app = typer.Typer(help="Explain ICT detections for a day")

def _rows(symbol, dataset, schema, et_date):
    TZ_ET = ZoneInfo("America/New_York")
    y,m,d = map(int, et_date.split("-"))
    s_et = datetime(y,m,d,0,0,tzinfo=TZ_ET)
    e_et = s_et + timedelta(days=1)
    return list(ohlcv_range(dataset, schema, symbol, s_et.astimezone(timezone.utc), clamp_end(e_et.astimezone(timezone.utc))))

@app.command("day")
def day(date: str = typer.Option(...,"--date","-d")):
    ds = os.getenv("DB_DATASET","GLBX.MDP3")
    sc = os.getenv("DB_SCHEMA","ohlcv-1m")
    sym = os.getenv("FRONT_SYMBOL","NQ?")
    div = int(os.getenv("PRICE_DIVISOR","1000000000"))
    ict = ICTDetector()
    rows = _rows(sym, ds, sc, date)
    for r in rows:
        tsn = getattr(r,"ts_event",None) or getattr(r,"ts_recv",None)
        ts = datetime.fromtimestamp(float(tsn)/1e9, tz=timezone.utc)
        o = float(getattr(r,"open",getattr(r,"o",0.0)))/div
        h = float(getattr(r,"high",getattr(r,"h",0.0)))/div
        l = float(getattr(r,"low", getattrib:=getattr(r,"l",0.0)))/div
        l = float(getattr(r,"low",getattr(r,"l",0.0)))/div
        c = float(getattr(r,"close",getattr(r,"c",0.0)))/div
        before_s = ict.stats_sweeps; before_f = ict.stats_fvgs
        sigs = ict.add_bar(ts,o,h,l,c)
        made_sweep = ict.stats_sweeps>before_s
        made_fvg   = ict.stats_fvgs>before_f
        if made_sweep or made_fvg or sigs:
            line = [ts.isoformat()]
            if made_sweep: line.append("SWEEP")
            if made_fvg:   line.append("FVG")
            for s in sigs: line.append(f"ENTRY {s.side} {s.entry:.2f}/{s.stop:.2f}")
            print(" | ".join(line))
    print(f"Totals: sweeps={ict.stats_sweeps} fvgs={ict.stats_fvgs} entries={ict.stats_entries}")
