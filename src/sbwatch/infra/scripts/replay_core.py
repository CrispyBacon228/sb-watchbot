# --- Replay Core (patched with safe date + safe fetch) ---
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
import os
from databento.common.error import BentoClientError
from sbwatch.alerts import dispatch   # must exist in sbw/
from sbwatch.levels import build_levels_for_day
from sbwatch.feed import get_historical, fetch_range
from sbwatch.timebox import make_utc_range, clamp_window, sort_by_ts

CONTRACT = os.getenv("FRONT_SYMBOL", "NQU5")
SCHEMA = os.getenv("DB_SCHEMA", "ohlcv-1m")
API_KEY = os.getenv("DATABENTO_API_KEY")

def _last_trading_day(today_et: date) -> date:
    """Pick the most recent weekday with data (Fri if weekend, yesterday otherwise)."""
    wd = today_et.weekday()  # Mon=0 … Sun=6
    if wd == 6:   # Sunday → Friday
        return today_et - timedelta(days=2)
    if wd == 5:   # Saturday → Friday
        return today_et - timedelta(days=1)
    return today_et - timedelta(days=1)  # Mon–Fri → yesterday

# Select the replay date
# Always take REPLAY_ET_DATE from env, default to yesterday if missing

from datetime import date, timedelta

import os



et_date_str = os.getenv("REPLAY_ET_DATE")

if not et_date_str:

    # fallback: yesterday in ET

    from zoneinfo import ZoneInfo

    today_et = date.today()

    et_date_str = (today_et - timedelta(days=1)).strftime("%Y-%m-%d")



REPLAY_ET_DATE = et_date_str

print(f"▶ Using fixed REPLAY_ET_DATE={REPLAY_ET_DATE}")

