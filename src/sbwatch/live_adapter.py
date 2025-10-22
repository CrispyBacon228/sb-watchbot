from __future__ import annotations
import os, time
from dataclasses import dataclass
from typing import Iterator
import databento as db

@dataclass
class Bar:
    ts_epoch_ms: int
    open: float
    high: float
    low: float
    close: float

def iter_live_bars(
    api_key: str | None = None,
    dataset: str | None = None,
    schema: str | None = None,
    symbol: str | None = None,
    price_divisor: float | None = None,
    run_seconds: int | None = None,  # None = run forever (service mode)
) -> Iterator[Bar]:
    """
    Subscribe to Databento Live and yield scaled OHLCV bars as Bar(ts_ms, o,h,l,c).
    This matches the probe logic (no .start() call; iteration auto-starts).
    """
    api_key       = api_key or os.getenv("DB_API_KEY")
    dataset       = dataset or os.getenv("DATASET", "GLBX.MDP3")
    schema        = schema  or os.getenv("SCHEMA",  "ohlcv-1m")
    symbol        = symbol  or os.getenv("SYMBOL",  "NQZ5")
    price_divisor = float(price_divisor or os.getenv("PRICE_DIVISOR", "1e9"))

    if not api_key:
        raise RuntimeError("DB_API_KEY not set")

    def scale(x):
        return None if x is None else float(x) / price_divisor

    live = db.Live(key=api_key)
    live.subscribe(dataset=dataset, schema=schema, symbols=symbol)

    deadline = time.time() + run_seconds if run_seconds else None
    for rec in live:
        if deadline and time.time() >= deadline:
            break

        ts_ns = getattr(rec, "ts_event", 0)
        o = scale(getattr(rec, "open",  None))
        h = scale(getattr(rec, "high",  None))
        l = scale(getattr(rec, "low",   None))
        c = scale(getattr(rec, "close", None))
        if not (ts_ns and o is not None and h is not None and l is not None and c is not None):
            continue

        yield Bar(
            ts_epoch_ms = int(int(ts_ns)/1_000_000),
            open  = o,
            high  = h,
            low   = l,
            close = c,
        )
