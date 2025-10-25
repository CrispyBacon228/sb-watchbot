from __future__ import annotations
import os, csv, json, sys, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sbwatch.strategy import SBEngine

ET = ZoneInfo("America/New_York")

# --- knobs (match probes; read from env) ---
DISP_MIN   = float(os.environ.get("SB_DISPLACEMENT_MIN", "0.30"))
FVG_MIN    = float(os.environ.get("SB_FVG_MIN",          "0.15"))
RET_MAX    = int(os.environ.get("SB_RET_MAX_BARS",       "20"))
PRE10      = os.environ.get("INTERNAL_SWEEP_PRE10","1") == "1"
FVG_MODE   = os.environ.get("FVG_MODE","3C").upper()
WIN_START  = os.environ.get("WINDOW_START", "10:00")
WIN_END    = os.environ.get("WINDOW_END",   "11:00")

def in_entry_window(ts:int)->bool:
    t=dt.datetime.fromtimestamp(ts/1000,tz=ET).time()
    s=dt.time.fromisoformat(WIN_START); e=dt.time.fromisoformat(WIN_END)
    return s<=t<=e

def iso(ts): 
    return dt.datetime.fromtimestamp(ts/1000,tz=ET).strftime("%H:%M:%S")

def load_levels(p:Path)->dict:
    payload = json.loads(p.read_text(encoding="utf-8"))
    return payload.get("levels") or payload  # accept raw dict too

def read_rows(csvp:Path):
    out=[]
    with csvp.open() as f:
        rdr=csv.DictReader(f)
        for r in rdr:
            out.append({"ts":int(r["ts_epoch_ms"]), "o":float(r["open"]),
                        "h":float(r["high"]), "l":float(r["low"]), "c":float(r["close"])})
    return out

def explain_like_candidates(rows, levels):
    PDH, PDL = levels.get("pdh"), levels.get("pdl")
    AHI, ALO = levels.get("asia_high"), levels.get("asia_low")
    LHI, LLO = levels.get("london_high"), levels.get("london_low")

    pre_hi = pre_lo = None
    if PRE10:
        for r in rows:
            t=dt.datetime.fromtimestamp(r["ts"]/1000,tz=ET)
            if t.hour<10:
                pre_hi = r["h"] if pre_hi is None or r["h"]>pre_hi else pre_hi
                pre_lo = r["l"] if pre_lo is None or r["l"]<pre_lo else pre_lo

    last_bull = None
    last_bear = None
    out = []

    for i in range(1, len(rows)):
        A = rows[i-2] if i >= 2 else None
        B = rows[i-1]
        C = rows[i]

        rngB = max(1e-9, B["h"]-B["l"]); dispB = abs(B["c"]-B["o"])/rngB
        rngC = max(1e-9, C["h"]-C["l"]); dispC = abs(C["c"]-C["o"])/rngC
        disp_ok = (dispB >= DISP_MIN) if FVG_MODE=="3C" else (dispC >= DISP_MIN)

        swept_hi = ((PDH and C["h"]>PDH) or (AHI and C["h"]>AHI) or (LHI and C["h"]>LHI) or (PRE10 and pre_hi and C["h"]>pre_hi))
        swept_lo = ((PDL and C["l"]<PDL) or (ALO and C["l"]<ALO) or (LLO and C["l"]<LLO) or (PRE10 and pre_lo and C["l"]<pre_lo))

        if FVG_MODE=="3C" and A and disp_ok:
            if C["l"] - A["h"] >= FVG_MIN:
                last_bull = {"i":i, "ts":C["ts"], "gap_top":C["l"], "gap_bot":A["h"]}
            if A["l"] - C["h"] >= FVG_MIN:
                last_bear = {"i":i, "ts":C["ts"], "gap_top":A["l"], "gap_bot":C["h"]}
        elif FVG_MODE!="3C" and disp_ok:
            if C["l"] - B["h"] >= FVG_MIN:
                last_bull = {"i":i, "ts":C["ts"], "gap_top":C["l"], "gap_bot":B["h"]}
            if B["l"] - C["h"] >= FVG_MIN:
                last_bear = {"i":i, "ts":C["ts"], "gap_top":B["l"], "gap_bot":C["h"]}

        if swept_lo and last_bull and i - last_bull["i"] <= RET_MAX and C["l"] <= last_bull["gap_top"]:
            if in_entry_window(C["ts"]):
                out.append((C["ts"], "LONG", last_bull["gap_top"]))
            last_bull = None

        if swept_hi and last_bear and i - last_bear["i"] <= RET_MAX and C["h"] >= last_bear["gap_bot"]:
            if in_entry_window(C["ts"]):
                out.append((C["ts"], "SHORT", last_bear["gap_bot"]))
            last_bear = None

    return out

def engine_candidates(rows, levels):
    from sbwatch import notify as _notify
    captured=[]
    def _fake_post_entry(*args, **kw):
        ts = kw.get("when") or (args[0] if args else None)
        side = (kw.get("side") or kw.get("direction") or "").upper() or "ENTRY"
        price = kw.get("price")
        if in_entry_window(ts):
            captured.append((ts, side, price))
    _notify.post_entry = _fake_post_entry

    eng = SBEngine(levels)
    for attr in ("armed","is_armed","allow_trades"):
        if hasattr(eng, attr): setattr(eng, attr, True)

    for r in rows:
        eng.on_bar(r["ts"], r["o"], r["h"], r["l"], r["c"])
    return captured

def main(csvp:Path, levelsp:Path):
    rows = read_rows(csvp)
    levels = load_levels(levelsp)
    pro = explain_like_candidates(rows, levels)
    eng = engine_candidates(rows, levels)

    Spro = {(t,s) for (t,s,_) in pro}
    Seng = {(t,s) for (t,s,_) in eng}

    only_pro = sorted(Spro - Seng)
    only_eng = sorted(Seng - Spro)
    both     = sorted(Spro & Seng)

    print("[EQUIV] settings:",
          dict(DISP_MIN=DISP_MIN, FVG_MIN=FVG_MIN, RET_MAX=RET_MAX,
               PRE10=PRE10, FVG_MODE=FVG_MODE, WIN_START=WIN_START, WIN_END=WIN_END))
    print(f"[EQUIV] probe candidates: {len(pro)}; engine candidates: {len(eng)}; intersection: {len(both)}")
    if both:
        shared = [f"{iso(t)} {s}" for (t, s) in both]
        print("  shared:", shared)
    if only_pro:
        probe_only = [f"{iso(t)} {s}" for (t, s) in only_pro]
        print("  probe_only:", probe_only)
    if only_eng:
        engine_only = [f"{iso(t)} {s}" for (t, s) in only_eng]
        print("  engine_only:", engine_only)

    ok = (Spro == Seng)
    print(f"[EQUIV] EXACT_MATCH={ok}")
    if not ok:
        print("[EQUIV] mismatch detail (first 10 each):")
        po = [f"{iso(t)} {s}" for (t,s) in only_pro[:10]]
        eo = [f"{iso(t)} {s}" for (t,s) in only_eng[:10]]
        print("  probe_only:", po)
        print("  engine_only:", eo)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python probes/alert_equivalence_check.py CSV [LEVELS_JSON]", file=sys.stderr)
        sys.exit(2)
    csvp = Path(sys.argv[1])
    lvls = Path(sys.argv[2]) if len(sys.argv)>2 else Path("/opt/sb-simple/data/levels.json")
    main(csvp, lvls)
