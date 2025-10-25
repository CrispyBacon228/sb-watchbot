from __future__ import annotations
import os, csv, json, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from sbwatch.strategy import SBEngine

ET=ZoneInfo("America/New_York")
DISP_MIN=float(os.environ.get("SB_DISPLACEMENT_MIN","0.4"))
FVG_MIN=float(os.environ.get("SB_FVG_MIN","0.25"))
RET_MAX=int(os.environ.get("SB_RET_MAX_BARS","10"))
INTERNAL_SWEEP_PRE10=os.environ.get("INTERNAL_SWEEP_PRE10","0")=="1"
FVG_MODE=os.environ.get("FVG_MODE","3C").upper()
WIN_START=os.environ.get("WINDOW_START"); WIN_END=os.environ.get("WINDOW_END")

def in_entry_window(ts:int)->bool:
    if not WIN_START and not WIN_END: return True
    t=dt.datetime.fromtimestamp(ts/1000,tz=ET).time()
    s=dt.time.fromisoformat(WIN_START) if WIN_START else dt.time(0,0)
    e=dt.time.fromisoformat(WIN_END) if WIN_END else dt.time(23,59,59)
    return s<=t<=e
def iso(ts): return dt.datetime.fromtimestamp(ts/1000,tz=ET).strftime("%H:%M")

def run(csvp:Path, lvlp:Path):
    levels=(json.loads(lvlp.read_text()) or {}).get("levels",{})
    print("[EXPLAIN] Levels used:", json.dumps(levels, sort_keys=True))
    eng=SBEngine(levels)

    rows=[]
    with csvp.open() as f:
        rdr=csv.DictReader(f)
        for r in rdr:
            rows.append({"ts":int(r["ts_epoch_ms"]),"o":float(r["open"]),
                         "h":float(r["high"]),"l":float(r["low"]),"c":float(r["close"])})

    PDH,PDL=levels.get("pdh"),levels.get("pdl")
    AHI,ALO=levels.get("asia_high"),levels.get("asia_low")
    LHI,LLO=levels.get("london_high"),levels.get("london_low")

    pre_hi=pre_lo=None
    if INTERNAL_SWEEP_PRE10:
        for r in rows:
            t=dt.datetime.fromtimestamp(r["ts"]/1000,tz=ET)
            if t.hour<10:
                pre_hi=r["h"] if pre_hi is None or r["h"]>pre_hi else pre_hi
                pre_lo=r["l"] if pre_lo is None or r["l"]<pre_lo else pre_lo

    last_bull=None; last_bear=None; found=0

    for i in range(1,len(rows)):
        A=rows[i-2] if i>=2 else None
        B=rows[i-1]; C=rows[i]
        eng.on_bar(C["ts"],C["o"],C["h"],C["l"],C["c"])  # parity

        rngB=max(1e-9,B["h"]-B["l"]); dispB=abs(B["c"]-B["o"])/rngB
        rngC=max(1e-9,C["h"]-C["l"]); dispC=abs(C["c"]-C["o"])/rngC
        disp_ok = (dispB>=DISP_MIN) if FVG_MODE=="3C" else (dispC>=DISP_MIN)

        swept_hi = ((PDH and C["h"]>PDH) or (AHI and C["h"]>AHI) or (LHI and C["h"]>LHI) or (INTERNAL_SWEEP_PRE10 and pre_hi and C["h"]>pre_hi))
        swept_lo = ((PDL and C["l"]<PDL) or (ALO and C["l"]<ALO) or (LLO and C["l"]<LLO) or (INTERNAL_SWEEP_PRE10 and pre_lo and C["l"]<pre_lo))

        if FVG_MODE=="3C" and A and disp_ok:
            if C["l"]-A["h"]>=FVG_MIN: last_bull={"i":i,"gap_top":C["l"],"gap_bot":A["h"],"disp":dispB}
            if A["l"]-C["h"]>=FVG_MIN: last_bear={"i":i,"gap_top":A["l"],"gap_bot":C["h"],"disp":dispB}
        elif FVG_MODE!="3C" and disp_ok:
            if C["l"]-B["h"]>=FVG_MIN: last_bull={"i":i,"gap_top":C["l"],"gap_bot":B["h"],"disp":dispC}
            if B["l"]-C["h"]>=FVG_MIN: last_bear={"i":i,"gap_top":B["l"],"gap_bot":C["h"],"disp":dispC}

        if swept_lo and last_bull and i-last_bull["i"]<=RET_MAX and C["l"]<=last_bull["gap_top"]:
            if in_entry_window(C["ts"]):
                print(f"[EXPLAIN] {iso(C['ts'])} LONG candidate (ret_to={last_bull['gap_top']:.2f} disp={last_bull['disp']:.2f} mode={FVG_MODE})")
                found+=1
            last_bull=None

        if swept_hi and last_bear and i-last_bear["i"]<=RET_MAX and C["h"]>=last_bear["gap_bot"]:
            if in_entry_window(C["ts"]):
                print(f"[EXPLAIN] {iso(C['ts'])} SHORT candidate (ret_to={last_bear['gap_bot']:.2f} disp={last_bear['disp']:.2f} mode={FVG_MODE})")
                found+=1
            last_bear=None

    print(f"[EXPLAIN] TOTAL CANDIDATES: {found}")
    print(f"[EXPLAIN] SBEngine entry_count attribute:", getattr(eng,"entry_count","n/a"))

if __name__=="__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]))
