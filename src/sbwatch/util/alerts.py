from __future__ import annotations
import os, csv
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_ET = ZoneInfo("America/New_York")
ALERTS_LOG_TEMPLATE = os.getenv("ALERTS_LOG_TEMPLATE", "./out/alerts_live_%Y-%m-%d.csv")

def alerts_log_path() -> str:
    """Return the alerts CSV path for 'now' in ET time."""
    return datetime.now(TZ_ET).strftime(ALERTS_LOG_TEMPLATE)

def append_alert(kind: str, symbol: str, price: float, level: Optional[float] = None) -> str:
    """
    Append a single alert row to today's alerts CSV. Returns the file path.
    Columns: ts_utc, symbol, kind, price, level
    """
    path = alerts_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    newfile = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if newfile:
            w.writerow(["ts_utc", "symbol", "kind", "price", "level"])
        w.writerow([
            datetime.utcnow().isoformat() + "+00:00",
            symbol,
            kind,
            f"{price:.2f}",
            "" if level is None else f"{level:.2f}",
        ])
    return path

# Optional helpers used by some live/ICT logs (no harm if unused)
def fmt_ict_entry(side: str, entry: float, stop: float, tp1: float, tp2: float) -> str:
    return f"ICT_{side.upper()}_ENTRY @ {entry:.2f} | stop {stop:.2f} | TP1 {tp1:.2f} | TP2 {tp2:.2f}"

def fmt_tp(side: str, tp_price: float) -> str:
    return f"ICT_{side.upper()}_TP @ {tp_price:.2f}"
