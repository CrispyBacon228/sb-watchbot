from __future__ import annotations
import os, csv
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_ET = ZoneInfo("America/New_York")
ALERTS_LOG_TEMPLATE = os.getenv("ALERTS_LOG_TEMPLATE", "./out/alerts_live_%Y-%m-%d.csv")

def alerts_log_path() -> str:
    return datetime.now(TZ_ET).strftime(ALERTS_LOG_TEMPLATE)

def append_alert(kind: str, symbol: str, price: float, level: float | None = None):
    path = alerts_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    newfile = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if newfile:
            w.writerow(["ts_utc","symbol","kind","price","level"])
        w.writerow([datetime.utcnow().isoformat()+"+00:00", symbol, kind, f"{price:.2f}", "" if level is None else f"{level:.2f}"])
