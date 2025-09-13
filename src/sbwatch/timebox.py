from datetime import datetime, timedelta, time
import pytz

ET = pytz.timezone("America/New_York")

def make_utc_range(day: datetime, start_hhmm: str, end_hhmm: str):
    s_h, s_m = map(int, start_hhmm.split(":"))
    e_h, e_m = map(int, end_hhmm.split(":"))
    s = ET.localize(datetime.combine(day.date(), time(s_h, s_m)))
    e = ET.localize(datetime.combine(day.date(), time(e_h, e_m)))
    return s.astimezone(pytz.UTC), e.astimezone(pytz.UTC)

def clamp_window(s, e, minutes=5):
    return s + timedelta(minutes=minutes), e - timedelta(minutes=minutes)

def sort_by_ts(df):
    return df.sort_values("ts") if df is not None and "ts" in df.columns else df
