import sys, pandas as pd
from zoneinfo import ZoneInfo
NY=ZoneInfo("America/New_York")
csv=sys.argv[1] if len(sys.argv)>1 else "out/replay_2025-10-03.csv"
df=pd.read_csv(csv,parse_dates=["timestamp"])
if df["timestamp"].dt.tz is None: df["timestamp"]=df["timestamp"].dt.tz_localize("UTC")
df["ny"]=df["timestamp"].dt.tz_convert(NY)

# 10–11 window
kz=df[(df["ny"].dt.hour==10)]
print("— Killzone rows:",len(kz))
print("  window_hi/lo:",kz["high"].max(),kz["low"].min())

# RTH 9:30–16:00
rth=df[(df["ny"].dt.time>=pd.to_datetime("09:30").time())&(df["ny"].dt.time<pd.to_datetime("16:00").time())].copy()
print("— RTH rows:",len(rth))
print("  rth_hi/lo:",rth["high"].max(),rth["low"].min())

# Simple sweep detector vs rolling prior high/low (last 60 bars)
lb=60
rth["prior_hi"]=rth["high"].rolling(lb, min_periods=1).max().shift(1)
rth["prior_lo"]=rth["low"].rolling(lb, min_periods=1).min().shift(1)
sw_hi=rth[rth["high"]>rth["prior_hi"]]
sw_lo=rth[rth["low"]<rth["prior_lo"]]
print("— Sweeps (within last 60 bars): hi:",len(sw_hi)," lo:",len(sw_lo))
print(sw_lo[["timestamp","high","low"]].tail(5).to_string(index=False))
print(sw_hi[["timestamp","high","low"]].tail(5).to_string(index=False))
