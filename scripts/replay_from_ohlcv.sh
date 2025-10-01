#!/usr/bin/env bash
set -euo pipefail
DATE="${1:-$(date -u +%F)}"
echo "Using DATE=${DATE}"

python - <<PY
import os, pytz
from datetime import datetime, timezone
from dotenv import load_dotenv
from databento import Historical
import pandas as pd
import pathlib

# --- env
load_dotenv("/opt/sb-watchbot/.env")
API_KEY   = os.environ["DATABENTO_API_KEY"]
DATASET   = os.environ.get("DATASET", "GLBX.MDP3")
SCHEMA    = os.environ.get("SCHEMA", "ohlcv-1m")
SYMBOL    = os.environ.get("SYMBOL", "NQZ5")
DIV       = int(os.environ.get("PRICE_DIVISOR","1"))
DATE_STR  = "${DATE}"  # <-- bash substitution works here

NY = pytz.timezone("America/New_York")
d  = datetime.strptime(DATE_STR, "%Y-%m-%d")
start_ny = NY.localize(datetime(d.year, d.month, d.day, 9, 30))
end_ny   = NY.localize(datetime(d.year, d.month, d.day, 16, 0))
start = start_ny.astimezone(timezone.utc)
end   = end_ny.astimezone(timezone.utc)

print(f"[fetch] {SYMBOL} {DATASET}/{SCHEMA} {start} -> {end}")

client = Historical(API_KEY)
df = client.timeseries.get_range(
    dataset=DATASET,
    schema=SCHEMA,
    symbols=[SYMBOL],
    stype_in="parent",
    start=start,
    end=end,
).to_df()

if df is None or df.empty:
    print("EMPTY result — no bars returned for that window.")
    raise SystemExit(0)

# normalize time column and scale prices
tcol = "timestamp" if "timestamp" in df.columns else ("time" if "time" in df.columns else None)
if tcol and tcol != "timestamp":
    df = df.rename(columns={tcol:"timestamp"})
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

for col in ("open","high","low","close"):
    if col in df.columns:
        df[col] = df[col] / DIV

# write CSV
outdir = pathlib.Path("out"); outdir.mkdir(exist_ok=True)
out = outdir / f"replay_{DATE_STR}.csv"
df[["timestamp","open","high","low","close","volume"]].to_csv(out, index=False)
print(f"Wrote -> {out}")

print("---- replay head ----")
print(pd.read_csv(out).head().to_string(index=False))
print("---- replay tail ----")
print(pd.read_csv(out).tail().to_string(index=False))
PY
