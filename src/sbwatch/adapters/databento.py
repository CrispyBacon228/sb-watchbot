from __future__ import annotations
import os, functools, re
from datetime import datetime, timezone, timedelta
from loguru import logger
from databento import Historical
from databento.common.error import BentoClientError

# how much to stay behind "now" by default (seconds)
DEFAULT_MARGIN_SEC = int(os.getenv("MARGIN_SEC", "600"))  # 10 min default

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
    """Clamp the requested end to (now - DEFAULT_MARGIN_SEC)."""
    now_cut = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_MARGIN_SEC)
    return min(end_utc, now_cut)

def _backoff_end_on_422(end_utc: datetime, err_text: str) -> datetime | None:
    """
    Try to parse 'available up to <timestamp>' from the error.
    If present, return a slightly earlier time; otherwise back off 2 minutes.
    """
    m = re.search(r"available up to [`']?([0-9:-]{19})(?:\+00:00)?", err_text)
    if m:
        # use the provider's available_end - 30s
        avail = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        return avail - timedelta(seconds=30)
    # generic backoff
    return end_utc - timedelta(minutes=2)

def ohlcv_range(dataset: str, schema: str, symbol: str,
                start_utc: datetime, end_utc: datetime):
    """
    Robust wrapper around timeseries.get_range with:
      - end clamped behind 'now' by DEFAULT_MARGIN_SEC
      - on 422 (end after available), back off the end and retry
    Returns an iterator on success; raises after a few attempts.
    """
    client = get_hist()
    start = start_utc
    end   = clamp_end(end_utc)

    attempts = 0
    max_attempts = 6  # ~ up to ~10-12 minutes of total backoff
    while attempts < max_attempts:
        try:
            return client.timeseries.get_range(
                dataset=dataset,
                schema=schema,          # e.g., "ohlcv-1m"
                symbols=symbol,         # e.g., "NQZ5"
                start=start,
                end=end,
            )
        except BentoClientError as e:
            msg = str(e)
            if "data_end_after_available_end" in msg or "end is after the available range" in msg:
                new_end = _backoff_end_on_422(end, msg)
                if new_end is None or new_end <= start:
                    logger.error("Backoff produced invalid window (start={}, end={})", start, new_end)
                    raise
                logger.warning("422 lag: backing off end to {}", new_end.isoformat())
                end = new_end
                attempts += 1
                continue
            # other errors bubble up
            raise
