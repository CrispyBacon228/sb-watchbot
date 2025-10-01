import os, sys
from datetime import datetime, timedelta, timezone
from databento import Historical
from zoneinfo import ZoneInfo
import pandas as pd

def et_today_bounds():
    et = ZoneInfo("America/New_York")
    now_et = datetime.now(tz=et)
    start_et = now_et.replace(hour=10, minute=0, second=0, microsecond=0)
    end_et   = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if now_et < start_et:
        start_et = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    if now_et < end_et:
        end_et = now_et
    return start_et, end_et

def to_utc(dt): return dt.astimezone(timezone.utc)

def fetch_ohlcv_today():
    dataset = os.getenv("DB_DATASET", "GLBX.MDP3")
    schema  = os.getenv("DB_SCHEMA", "ohlcv-1m")
    symbol  = os.getenv("FRONT_SYMBOL", "NQZ25")
    divisor = int(os.getenv("PRICE_DIVISOR", "1"))
    margin  = int(os.getenv("END_MARGIN_SECONDS", "600"))

    start_et, end_et = et_today_bounds()
    start_utc, end_utc = to_utc(start_et), to_utc(end_et) - timedelta(seconds=margin)

    # FIXED: no api_key param, reads DATABENTO_API_KEY from env
    client = Historical()
    print(f"Pulling {symbol} from {start_utc} → {end_utc}")

    data = client.timeseries.get_range(
        dataset=dataset, schema=schema, symbols=symbol,
        start=start_utc, end=end_utc
    )
    df = data.to_df()
    for c in ["open","high","low","close"]:
        if c in df.columns:
            df[c] /= divisor

    out = f"ohlcv_{symbol}_{start_et:%Y%m%d}.csv"
    df.to_csv(out, index=False)
    print(f"Saved {len(df)} rows to {out}")
    print(df.head())

if __name__ == "__main__":
    fetch_ohlcv_today()
