from __future__ import annotations
import os, functools
from datetime import datetime, timezone, timedelta
from loguru import logger
from databento import Historical

def _mask(s: str, keep: int = 4) -> str:
    if not s: return ""
    return ("*" * max(0, len(s) - keep)) + s[-keep:]

@functools.lru_cache(maxsize=1)
def get_hist() -> Historical:
    key = os.getenv("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY missing in environment")
    try:
        client = Historical(key)   # some versions accept positional
    except TypeError:
        os.environ["DATABENTO_API_KEY"] = key
        client = Historical()      # others read from env
    logger.info("Databento client ready (key={})", _mask(key))
    return client

def clamp_end(end_utc: datetime) -> datetime:
    now_cut = datetime.now(timezone.utc) - timedelta(seconds=120)
    return min(end_utc, now_cut)

def ohlcv_range(dataset: str, schema: str, symbol: str,
                start_utc: datetime, end_utc: datetime):
    """Return iterator of rows with fields including high/low."""
    client = get_hist()
    end = clamp_end(end_utc)
    return client.timeseries.get_range(
        dataset=dataset,
        schema=schema,          # e.g., "ohlcv-1m"
        symbols=symbol,         # e.g., "NQZ5"
        start=start_utc,
        end=end,
    )
