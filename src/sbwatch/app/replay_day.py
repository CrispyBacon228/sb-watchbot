import os
from datetime import datetime, timezone
import pytz
import pandas as pd
from dotenv import load_dotenv

# use the working fetcher we just installed
from sbwatch.data.db_fetch import fetch_range, NY

load_dotenv("/opt/sb-watchbot/.env")

def main(date_str: str):
    # session window 09:30–16:00 NY
    d = datetime.strptime(date_str, "%Y-%m-%d")
    start = NY.localize(datetime(d.year, d.month, d.day, 9, 30)).astimezone(timezone.utc)
    end   = NY.localize(datetime(d.year, d.month, d.day, 16, 0)).astimezone(timezone.utc)

    df = fetch_range(start, end)
    if df is None or df.empty:
        print(f"EMPTY result for {date_str}")
        return

    os.makedirs("out", exist_ok=True)
    out = f"out/replay_{date_str}.csv"
    cols = [c for c in ("timestamp","open","high","low","close","volume") if c in df.columns]
    df[cols].to_csv(out, index=False)
    print(f"Wrote -> {out}")

    try:
        print("---- head ----")
        print(pd.read_csv(out).head().to_string(index=False))
        print("---- tail ----")
        print(pd.read_csv(out).tail().to_string(index=False))
    except Exception:
        pass

if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    print(f"Using DATE={date_arg}")
    main(date_arg)
