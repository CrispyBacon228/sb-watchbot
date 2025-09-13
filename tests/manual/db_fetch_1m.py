import os, sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from databento import Historical
from databento.common.error import BentoClientError

API = os.environ.get("DATABENTO_API_KEY")
DATASET = os.environ.get("DB_DATASET", "GLBX.MDP3")
SCHEMA  = os.environ.get("DB_SCHEMA",  "ohlcv-1m")
SYMBOL  = os.environ.get("FRONT_SYMBOL", "NQZ5")  # whatever you want to test
DATE_ET = os.environ.get("REPLAY_ET_DATE", datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))

if not API:
    print("DATABENTO_API_KEY not set"); sys.exit(2)

tz_et, tz_utc = ZoneInfo("America/New_York"), ZoneInfo("UTC")
d = datetime.strptime(DATE_ET, "%Y-%m-%d").date()
start_et = datetime.combine(d, time(9,30), tz_et)
end_et   = datetime.combine(d, time(11,0), tz_et)
start_utc, end_utc = start_et.astimezone(tz_utc), end_et.astimezone(tz_utc)

# clamp end to midnight next UTC (prevents running off dataset when markets close early)
midnight_next = datetime.combine(d, time(0,0), tz_utc) + timedelta(days=1)
if end_utc > midnight_next:
    end_utc = midnight_next

client = Historical(key=API)

def try_get(start, end):
    return client.timeseries.get_range(
        dataset=DATASET, schema=SCHEMA, symbols=SYMBOL, start=start, end=end
    )

step = timedelta(minutes=10)
attempts = 18
ok = None
cur_end = end_utc
for i in range(attempts):
    try:
        print(f"Trying: {start_utc.isoformat()} -> {cur_end.isoformat()}")
        recs = try_get(start_utc, cur_end)
        ok = recs
        break
    except BentoClientError as e:
        msg = str(e)
        # push end backwards when we see after-available-end; otherwise widen start a tad
        if "after_available" in msg:
            cur_end -= step
            continue
        if "start_on_or_after_end" in msg or "start_after_available_end" in msg:
            start_utc = cur_end - timedelta(minutes=30)
            continue
        raise

if ok is None:
    print("Failed to fetch after clamping attempts"); sys.exit(1)

# For ohlcv-1m, ok is an iterator of small records; count a few
count = 0
for _ in ok:
    count += 1
    if count >= 10: break

print("✅ DB fetch OK — read at least", count, "records")
