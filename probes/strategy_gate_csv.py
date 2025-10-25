from __future__ import annotations
import os, sys, csv, json, traceback, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# knobs
DISP_MIN  = float(os.environ.get("SB_DISPLACEMENT_MIN", "0.25"))
FVG_MIN   = float(os.environ.get("SB_FVG_MIN", "0.10"))
RET_MAX   = int(os.environ.get("SB_RET_MAX_BARS", "30"))
INTERNAL_SWEEP_PRE10 = os.environ.get("INTERNAL_SWEEP_PRE10","0") == "1"
IGNORE_SWEEP         = os.environ.get("IGNORE_SWEEP","0") == "1"
FVG_MODE             = os.environ.get("FVG_MODE","3C").upper()  # "3C" or "2C"

# entries-only window (plumbing is full day)
WIN_START = os.environ.get("WINDOW_START")   # e.g. "10:00"
WIN_END   = os.environ.get("WINDOW_END")     # e.g. "11:00"

def iso(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms/1000, tz=ET).strftime("%H:%M")

def in_entry_window(ts_ms: int) -> bool:
    if not WIN_START and not WIN_END:
        return True
    t = dt.datetime.fromtimestamp(ts_ms/1000, tz=ET).time()
    s = dt.time.fromisoformat(WIN_START) if WIN_START else dt.time(0,0)
    e = dt.time.fromisoformat(WIN_END)   if WIN_END   else dt.time(23,59,59)
    return s <= t <= e

def load_levels(p: Path) -> dict:
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return d.get("levels") or {}

def read_csv(path: Path):
    rows=[]
    with path.open() as f:
        rdr=csv.DictReader(f)
        for r in rdr:
            rows.append({
                "ts": int(r["ts_epoch_ms"]),
                "o": float(r["open"]), "h": float(r["high"]),
                "l": float(r["low"]),  "c": float(r["close"]),
            })
    return rows

def swept_high(h, PDH, AHI, LHI, pre_hi):
    if IGNORE_SWEEP: return True, "ignore"
    src=[]
    if PDH is not None and h>PDH: src.append("PDH")
    if AHI is not None and h>AHI: src.append("asia_high")
    if LHI is not None and h>LHI: src.append("london_high")
    if INTERNAL_SWEEP_PRE10 and pre_hi is not None and h>pre_hi: src.append("pre10_hi")
    return (len(src)>0, ",".join(src))

def swept_low(l, PDL, ALO, LLO, pre_lo):
    if IGNORE_SWEEP: return True, "ignore"
    src=[]
    if PDL is not None and l<PDL: src.append("PDL")
    if ALO is not None and l<ALO: src.append("asia_low")
    if LLO is not None and l<LLO: src.append("london_low")
    if INTERNAL_SWEEP_PRE10 and pre_lo is not None and l<pre_lo: src.append("pre10_lo")
    return (len(src)>0, ",".join(src))

def show(label, arr, n=30):
    print(f"[GATE] {label}: {len(arr)}")
    for s in arr[:n]:
        print("   ", s)
    if len(arr)>n:
        print("   … (+%d more)" % (len(arr)-n))

def run(csv_path: Path, levels_path: Path):
    print(f"[GATE] CSV={csv_path} levels={levels_path}")
    rows = read_csv(csv_path)
    L    = load_levels(levels_path)
    print(f"[GATE] rows={len(rows)} knobs: DISP_MIN={DISP_MIN} FVG_MIN={FVG_MIN} RET_MAX={RET_MAX} "
          f"FVG_MODE={FVG_MODE} IGNORE_SWEEP={IGNORE_SWEEP} INTERNAL_SWEEP_PRE10={INTERNAL_SWEEP_PRE10} "
          f"WINDOW_START={WIN_START} WINDOW_END={WIN_END}")

    PDH, PDL = L.get("pdh"), L.get("pdl")
    AHI, ALO = L.get("asia_high"), L.get("asia_low")
    LHI, LLO = L.get("london_high"), L.get("london_low")

    # pre-10 anchors
    pre_hi = pre_lo = None
    if INTERNAL_SWEEP_PRE10:
        for r in rows:
            t = dt.datetime.fromtimestamp(r["ts"]/1000, tz=ET)
            if t.hour < 10:
                pre_hi = r["h"] if pre_hi is None or r["h"] > pre_hi else pre_hi
                pre_lo = r["l"] if pre_lo is None or r["l"] < pre_lo else pre_lo

    disp_events=[]; sweep_events=[]; fvg_events=[]; ret_events=[]; candidates=[]
    bull_fvgs=[];  bear_fvgs=[]

    for i in range(1, len(rows)):
        A = rows[i-2] if i >= 2 else None
        B = rows[i-1]
        C = rows[i]

        rngB = max(1e-9, B["h"] - B["l"]); dispB = abs(B["c"] - B["o"]) / rngB
        rngC = max(1e-9, C["h"] - C["l"]); dispC = abs(C["c"] - C["o"]) / rngC
        disp_ok = (dispB >= DISP_MIN) if FVG_MODE == "3C" else (dispC >= DISP_MIN)
        if disp_ok:
            disp_val = dispB if FVG_MODE == "3C" else dispC
            disp_events.append(f"{iso(C['ts'])} disp={disp_val:.2f}")

        hi_sw, hi_src = swept_high(C["h"], PDH, AHI, LHI, pre_hi)
        lo_sw, lo_src = swept_low (C["l"], PDL, ALO, LLO, pre_lo)
        if hi_sw: sweep_events.append(f"{iso(C['ts'])} sweep HIGH [{hi_src}]")
        if lo_sw: sweep_events.append(f"{iso(C['ts'])} sweep LOW  [{lo_src}]")

        # FVG creation
        if FVG_MODE == "3C" and A is not None and disp_ok:
            if C["l"] - A["h"] >= FVG_MIN:
                bull_fvgs.append({"i":i, "ts":C["ts"], "gap_top":C["l"], "gap_bot":A["h"]})
                fvg_events.append(f"{iso(C['ts'])} BULL FVG(3C) gap={C['l']-A['h']:.2f}")
            if A["l"] - C["h"] >= FVG_MIN:
                bear_fvgs.append({"i":i, "ts":C["ts"], "gap_top":A["l"], "gap_bot":C["h"]})
                fvg_events.append(f"{iso(C['ts'])} BEAR FVG(3C) gap={A['l']-C['h']:.2f}")
        elif FVG_MODE != "3C" and disp_ok:
            if C["l"] - B["h"] >= FVG_MIN:
                bull_fvgs.append({"i":i, "ts":C["ts"], "gap_top":C["l"], "gap_bot":B["h"]})
                fvg_events.append(f"{iso(C['ts'])} BULL FVG(2C) gap={C['l']-B['h']:.2f}")
            if B["l"] - C["h"] >= FVG_MIN:
                bear_fvgs.append({"i":i, "ts":C["ts"], "gap_top":B["l"], "gap_bot":C["h"]})
                fvg_events.append(f"{iso(C['ts'])} BEAR FVG(2C) gap={B['l']-C['h']:.2f}")

        # Returns → FVG (entries only gated by time window)
        if bull_fvgs:
            last = bull_fvgs[-1]
            if i - last["i"] <= RET_MAX and C["l"] <= last["gap_top"] and lo_sw:
                ret_events.append(f"{iso(C['ts'])} LONG return→FVG")
                if in_entry_window(C["ts"]):
                    candidates.append(f"{iso(C['ts'])} LONG ret_to={last['gap_top']:.2f} sweep_low={lo_src or 'ignore'}")
                bull_fvgs.clear()

        if bear_fvgs:
            last = bear_fvgs[-1]
            if i - last["i"] <= RET_MAX and C["h"] >= last["gap_bot"] and hi_sw:
                ret_events.append(f"{iso(C['ts'])} SHORT return→FVG")
                if in_entry_window(C["ts"]):
                    candidates.append(f"{iso(C['ts'])} SHORT ret_to={last['gap_bot']:.2f} sweep_high={hi_src or 'ignore'}")
                bear_fvgs.clear()

    print("\n===== GATE REPORT =====")
    show("Displacement bars", disp_events)
    show("Sweeps",           sweep_events)
    show("FVG creations",    fvg_events)
    show("Returns to FVG",   ret_events)
    show("ENTRY CANDIDATES (windowed)", candidates)
    print("=======================")

if __name__ == "__main__":
    try:
        csvp = Path(sys.argv[1])
        lvlp = Path(sys.argv[2]) if len(sys.argv)>2 else Path("/opt/sb-simple/data/levels.json")
        run(csvp, lvlp)
    except Exception as e:
        print("[GATE][ERROR]", e)
        traceback.print_exc()
        sys.exit(1)
