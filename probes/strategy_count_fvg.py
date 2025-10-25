from __future__ import annotations
import csv, sys, datetime as dt
from zoneinfo import ZoneInfo
ET=ZoneInfo("America/New_York")
FVG_MIN=float(__import__("os").environ.get("SB_FVG_MIN","0.25"))
DISP_MIN=float(__import__("os").environ.get("SB_DISPLACEMENT_MIN","0.4"))
def iso(ts): return dt.datetime.fromtimestamp(ts/1000, tz=ET).strftime("%H:%M")
rows=[]
with open(sys.argv[1]) as f:
    rdr=csv.DictReader(f)
    for r in rdr:
        rows.append({k:float(r[k]) if k!="ts_epoch_ms" else int(r[k]) for k in r})
bull=bear=0
for i in range(1,len(rows)):
    po,ph,pl,pc=rows[i-1]["open"],rows[i-1]["high"],rows[i-1]["low"],rows[i-1]["close"]
    ts,o,h,l,c=rows[i]["ts_epoch_ms"],rows[i]["open"],rows[i]["high"],rows[i]["low"],rows[i]["close"]
    rng=max(1e-9,h-l); body=abs(c-o)
    if body/rng>=DISP_MIN:
        if l-ph>=FVG_MIN: bull+=1; print(f"{iso(ts)} bull FVG gap={l-ph:.2f}")
        if pl-h>=FVG_MIN: bear+=1; print(f"{iso(ts)} bear FVG gap={pl-h:.2f}")
print(f"TOTAL bull={bull} bear={bear}")
