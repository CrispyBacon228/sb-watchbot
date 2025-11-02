import os
from pathlib import Path
from probes.strategy_explain_csv import run as explain_run

CSV = Path(os.environ.get("CSV",""))
if not CSV.exists():
    raise SystemExit(f"No CSV found: {CSV}")

LEVELS = Path("data/levels.json")
if not LEVELS.exists():
    print("WARN: data/levels.json missing — creating empty file")
    LEVELS.write_text('{"levels":{}}')

TICK_SIZE = float(os.environ.get("TICK_SIZE", "0.25"))
SL_TICKS  = int(os.environ.get("SB_SL_TICKS", "0"))

def _fmt(x):
    try: return f"{float(x):.2f}"
    except: return "-"

def _c1_sl(side, last):
    side = (side or "").upper()
    lo = last.get("c1_low")
    hi = last.get("c1_high")
    if side == "LONG"  and isinstance(lo,(int,float)):
        return float(lo) - SL_TICKS*TICK_SIZE
    if side == "SHORT" and isinstance(hi,(int,float)):
        return float(hi) + SL_TICKS*TICK_SIZE
    return None

def main():
    rows = list(explain_run(CSV, LEVELS))
    print(" ret   side  fvg   c1_lo   c1_hi   SL(C1)   SL(engine)")
    for r in rows:
        last = r.get("last",{}) or {}
        side = (r.get("side","") or "").upper()
        sl_c1  = _c1_sl(side,last)
        eng_sl = r.get("sl")
        print(f"{r.get('t','--'):>5}  {side:<5} {r.get('fvg','--'):>5} "
              f"{_fmt(last.get('c1_low')):>6} {_fmt(last.get('c1_high')):>6} "
              f"{_fmt(sl_c1):>7} {_fmt(eng_sl):>10}")

if __name__ == "__main__":
    main()
