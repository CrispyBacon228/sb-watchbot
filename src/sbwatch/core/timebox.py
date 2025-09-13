from __future__ import annotations
from datetime import datetime, time
from zoneinfo import ZoneInfo

def parse_hhmm(s: str) -> time:
    hh, mm = map(int, s.split(":"))
    return time(hh, mm)

def in_window(dt_utc: datetime, tz: str, start_hhmm: str, end_hhmm: str) -> bool:
    local = dt_utc.astimezone(ZoneInfo(tz))
    t = local.time()
    return parse_hhmm(start_hhmm) <= t <= parse_hhmm(end_hhmm)

def in_ny_killzone(dt_utc: datetime, tz: str, start_hhmm: str, end_hhmm: str) -> bool:
    return in_window(dt_utc, tz, start_hhmm, end_hhmm)
