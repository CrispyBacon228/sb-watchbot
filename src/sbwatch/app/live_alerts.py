import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv
from databento import Historical

# strategy = same engine replay uses
from sbwatch.strategy import on_bar  # on_bar(row) -> list[alerts] or None

# optional discord
def notify_discord(text: str):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        return
    try:
        import requests  # in venv already
        requests.post(url, json={"content": text}, timeout=5)
    except Exception:
        pass

def fmt_alerts(alerts):
    # alerts from on_bar already formatted in replay; keep a defensive path here
    if isinstance(alerts, str):
        return alerts
    if not alerts:
        return None
    return "\n".join(str(a) for a in alerts)

def now_floor_min_utc():
    t = datetime.now(timezone.utc)
    return t.replace(second=0, microsecond=0)

def main():
    load_dotenv("/opt/sb-watchbot/.env")
    dataset = os.getenv("DATASET", "GLBX.MDP3")
    schema  = os.getenv("SCHEMA", "ohlcv-1m")
    symbol  = os.getenv("SYMBOL", "NQZ5")

    client = Historical(os.environ["DATABENTO_API_KEY"])

    NY = ZoneInfo("America/New_York")

    print(f"[live] running {dataset}/{schema} {symbol}")

    # track the last processed bar ts to avoid duplicates
    last_ts = None

    # polling loop: pull the last *closed* minute repeatedly
    while True:
        try:
            # last closed minute in UTC
            end_utc = now_floor_min_utc()
            start_utc = end_utc - timedelta(minutes=1)

            df = client.timeseries.get_range(
                dataset=dataset,
                schema=schema,
                symbols=[symbol],
                start=start_utc,
                end=end_utc,
            ).to_df()

            if not df.empty:
                # normalise column names if needed
                cols = {c.lower(): c for c in df.columns}
                ts_col = None
                for k in ("timestamp", "time", "ts_event", "ts_recv", "ts_exchange"):
                    if k in cols:
                        ts_col = cols[k]
                        break
                if not ts_col:
                    raise KeyError("No time column in live df")

                # make sure we only process new bar(s)
                df = df.sort_values(ts_col)
                for _, row in df.iterrows():
                    ts = pd.to_datetime(row[ts_col], utc=True)
                    # skip if we've already processed this bar
                    if last_ts is not None and ts <= last_ts:
                        continue

                    # KILLZONE: filter to NY session window (adjust to your rules)
                    ny_time = ts.astimezone(NY).time()
                    if ny_time < datetime(2000,1,1,10,0).time() or ny_time >= datetime(2000,1,1,11,0).time():
                        last_ts = ts
                        continue

                    alerts = on_bar(row)
                    msg = fmt_alerts(alerts)
                    if msg:
                        print(msg, flush=True)
                        notify_discord(msg)

                    last_ts = ts
        except Exception as e:
            print(f"[live] error: {e}", flush=True)

        # sleep a few seconds; loop again
        time.sleep(5)

if __name__ == "__main__":
    main()
