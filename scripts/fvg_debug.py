import sys,pandas as pd
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
CSV=sys.argv[1] if len(sys.argv)>1 else "out/replay_2025-10-03.csv"
MIN_DISP=1.25; MIN_ZONE=1.00; LOOK=120; WIN=12

df=pd.read_csv(CSV,parse_dates=["timestamp"])
if df["timestamp"].dt.tz is None: df["timestamp"]=df["timestamp"].dt.tz_localize("UTC")
df["ny"]=df["timestamp"].dt.tz_convert(NY)
rth=df[(df["ny"].dt.time>=pd.to_datetime("09:30").time())&(df["ny"].dt.time<pd.to_datetime("16:00").time())].reset_index(drop=True)
kz=rth[(rth["ny"].dt.time>=pd.to_datetime("10:00").time())&(rth["ny"].dt.time<pd.to_datetime("11:00").time())].copy()
kz["i_full"]=kz.index
def swept_low(i):
  if i<1: return False
  lo=max(0,i-LOOK); prior=rth.loc[lo:i-1,"low"].min()
  return float(rth.loc[i,"low"])<float(prior)
def swept_high(i):
  if i<1: return False
  lo=max(0,i-LOOK); prior=rth.loc[lo:i-1,"high"].max()
  return float(rth.loc[i,"high"])>float(prior)
def recent_sweep_low(i):
  lo=max(0,i-WIN); return any(swept_low(j) for j in range(lo,i+1))
def recent_sweep_high(i):
  lo=max(0,i-WIN); return any(swept_high(j) for j in range(lo,i+1))
def low_extreme(i):
  lo=max(0,i-WIN); xs=[float(rth.loc[j,"low"]) for j in range(lo,i+1) if swept_low(j)]
  return min(xs) if xs else None
def high_extreme(i):
  lo=max(0,i-WIN); xs=[float(rth.loc[j,"high"]) for j in range(lo,i+1) if swept_high(j)]
  return max(xs) if xs else None

print(f"Killzone rows={len(kz)}")
for i in range(2,len(kz)):
  i0=int(kz.loc[i-2,"i_full"]); i2=int(kz.loc[i,"i_full"])
  c0=rth.loc[i0]; c2=rth.loc[i2]
  disp=float(c2["high"])-float(c2["low"])
  if disp<MIN_DISP: continue
  # bullish gap
  if float(c0["high"])<float(c2["low"]):
    zlo=float(c0["high"]); zhi=float(c2["low"])
    if (zhi-zlo)>=MIN_ZONE and recent_sweep_low(i2):
      se=low_extreme(i2)
      print(f"[FVG] {kz.loc[i,'timestamp']} LONG  zone=({zlo:.2f},{zhi:.2f})  sweep_ext={se:.2f}")
  # bearish gap
  if float(c2["high"])<float(c0["low"]):
    zlo=float(c2["high"]); zhi=float(c0["low"])
    if (zhi-zlo)>=MIN_ZONE and recent_sweep_high(i2):
      se=high_extreme(i2)
      print(f"[FVG] {kz.loc[i,'timestamp']} SHORT zone=({zlo:.2f},{zhi:.2f})  sweep_ext={se:.2f}")
