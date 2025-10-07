from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ_ET  = ZoneInfo("America/New_York")
TZ_UTC = ZoneInfo("UTC")

@dataclass(frozen=True)
class Window:
    start: time
    end: time

ASIA   = Window(time(20,0), time(0,0))    # 20:00–00:00 ET
LONDON = Window(time(2,0),  time(5,0))    # 02:00–05:00 ET
RTH    = Window(time(9,30), time(11, 5))   # 09:30–16:00 ET

def et_midnight(date_et_str: str | None) -> datetime:
    if date_et_str:
        y,m,d = map(int, date_et_str.split("-"))
        return datetime(y,m,d, tzinfo=TZ_ET)
    now_et = datetime.now(TZ_ET)
    return datetime(now_et.year, now_et.month, now_et.day, tzinfo=TZ_ET)

def prev_business_day_midnight(date_et: datetime) -> datetime:
    d = date_et
    while True:
        d = d - timedelta(days=1)
        if d.weekday() < 5:
            return d

def et_window_to_utc_range(et_mid: datetime, w: Window):
    s_et = datetime.combine(et_mid.date(), w.start, tzinfo=TZ_ET)
    e_et = datetime.combine(et_mid.date(), w.end,   tzinfo=TZ_ET)
    if w.end <= w.start:  # crosses midnight
        e_et += timedelta(days=1)
    return (s_et.astimezone(TZ_UTC), e_et.astimezone(TZ_UTC))
