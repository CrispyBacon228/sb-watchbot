from __future__ import annotations
from datetime import datetime, time
from dateutil import tz

NY = tz.gettz("America/New_York")

def now_et() -> datetime:
    return datetime.now(tz=NY)

def parse_hhmm(s: str) -> time:
    h, m = s.split(":"); return time(int(h), int(m), tzinfo=NY)

def in_range(now: datetime, start: time, end: time) -> bool:
    st = now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    en = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return st <= now <= en

def is_us_session(now: datetime, st="09:30", en="16:00") -> bool:
    return in_range(now, parse_hhmm(st), parse_hhmm(en))

def is_pre10_trade_window(now: datetime) -> bool:
    return in_range(now, parse_hhmm("09:30"), parse_hhmm("10:00"))

def is_sb_window(now: datetime) -> bool:
    return in_range(now, parse_hhmm("10:00"), parse_hhmm("11:00"))

def is_after_11(now: datetime) -> bool:
    return now >= now.replace(hour=11, minute=0, second=0, microsecond=0)

def london_end_et() -> time:
    return parse_hhmm("05:00")

def is_after_london_to_10(now: datetime) -> bool:
    return in_range(now, london_end_et(), parse_hhmm("10:00"))
