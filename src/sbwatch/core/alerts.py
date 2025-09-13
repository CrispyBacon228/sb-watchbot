from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

def _et_hms(ts_iso: str, tz: str = "America/New_York") -> str:
    """Convert ISO timestamp (UTC or with offset) to HH:MM:SS in ET."""
    if ts_iso.endswith("Z"):
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(ts_iso)
    et = dt.astimezone(ZoneInfo(tz))
    return et.strftime("%H:%M:%S")

@dataclass
class TradeAlert:
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    r_multiple: float
    basis: str
    ts: str                         # ISO time of the bar (UTC)
    label: str = "Silver Bullet Entry (Displacement)"

def format_discord(a: TradeAlert) -> str:
    t = _et_hms(a.ts)
    return (
        f"✅ {a.label}\n"
        f"*Level*: **{a.basis}**\n"
        f"*Side*: **{a.side}**\n"
        f"*Time (ET)*: {t}\n"
        f"*Entry*: {a.entry}\n"
        f"*Stop*: {a.stop}\n"
        f"*TP1*: {a.tp1}\n"
        f"*TP2*: {a.tp2}\n"
        f"*R*: {a.r_multiple}\n"
    )
