from __future__ import annotations

from typing import Iterator, Optional
from datetime import datetime, timezone
import csv
import inspect
import logging as log

class Tick:
    __slots__ = ("ts", "price", "size", "side")

    def __init__(self, ts: datetime, price: float, size: float = 1.0, side: Optional[str] = None):
        self.ts = ts
        self.price = price
        self.size = size
        self.side = side

def dry_run_ticks(csv_path: str) -> Iterator[Tick]:
    import csv
    log.warning("DRY-RUN: streaming ticks from {%s}", csv_path)
    with open(csv_path) as f:
        r = csv.reader(f); _ = next(r, None)
        for row in r:
            ts = datetime.fromisoformat(row[0])
            px = float(row[1])
            yield Tick(ts=ts, price=px)

def live_ticks(databento_key: str, symbol: str) -> Iterator[Tick]:
    """
    Stream real-time ticks from Databento Live.
    Always import Live via our shim so we’re insulated from upstream package layout changes.
    """
    try:
        from sbw.db_live import Live   # <— our shim
    except Exception as e:
        raise RuntimeError(f"Databento live import failed: {e}") from e

    log.info("Connecting to Databento Live…")
    client = Live(key=databento_key)

    dataset = "GLBX.MDP3"
    schema = "mbp-1"

    client.subscribe(dataset=dataset, schema=schema, symbols=[symbol])
    for msg in client:
        try:
            px = float(getattr(msg, "price", None))
            if px is None:
                continue
            ts = datetime.fromtimestamp(msg.ts / 1e9, tz=timezone.utc)
            yield Tick(ts=ts, price=px, size=getattr(msg, "size", 1.0))
        except Exception:
            # Be tolerant of odd frames; keep streaming
            continue
