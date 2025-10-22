import os, sys, time, csv
from datetime import datetime
import databento as db
from zoneinfo import ZoneInfo

API_KEY = os.getenv("DB_API_KEY")
DATASET = os.getenv("DATASET", "GLBX.MDP3")
SCHEMA  = os.getenv("SCHEMA",  "ohlcv-1m")
SYMBOL  = os.getenv("SYMBOL",  "NQZ5")
DIVISOR = float(os.getenv("PRICE_DIVISOR", "1e9"))
CSV_OUT = os.getenv("PROBE_CSV", "data/live_probe.csv")
TZ      = ZoneInfo(os.getenv("PROBE_TZ", "America/New_York"))

if not API_KEY:
    print("ERROR: DB_API_KEY not set (check /etc/sb-watchbot.env)", file=sys.stderr)
    sys.exit(2)

def scale(x):
    try:
        return None if x is None else float(x) / DIVISOR
    except Exception:
        return None

print(f"Connecting live: dataset={DATASET} schema={SCHEMA} symbol={SYMBOL}", flush=True)

# Prepare CSV (write header if empty/new)
need_header = not os.path.exists(CSV_OUT) or os.path.getsize(CSV_OUT) == 0
csv_f = open(CSV_OUT, "a", newline="")
writer = csv.writer(csv_f)
if need_header:
    writer.writerow(["ts_iso","ts_epoch_ms","open","high","low","close"])

live = db.Live(key=API_KEY)
live.subscribe(dataset=DATASET, schema=SCHEMA, symbols=SYMBOL)  # do NOT call start()

end_at = time.time() + 240  # ~4 minutes
try:
    for rec in live:  # iteration auto-starts the stream
        if time.time() >= end_at:
            break

        ts_ns = getattr(rec, "ts_event", 0)
        if not ts_ns:
            continue

        # Convert to ET and epoch ms
        ts_epoch_ms = int(int(ts_ns) / 1_000_000)
        ts_iso = datetime.fromtimestamp(ts_epoch_ms / 1000, tz=TZ).isoformat()

        o = scale(getattr(rec, "open",  None))
        h = scale(getattr(rec, "high",  None))
        l = scale(getattr(rec, "low",   None))
        c = scale(getattr(rec, "close", None))

        # Only proceed if we have a full bar
        if None in (o, h, l, c):
            continue

        # Print a labeled single-line summary for humans/logs
        print(f"[BAR] ts={ts_iso}  open={o:.2f} high={h:.2f} low={l:.2f} close={c:.2f}", flush=True)

        # Append to CSV (strategy-friendly)
        writer.writerow([ts_iso, ts_epoch_ms, f"{o:.2f}", f"{h:.2f}", f"{l:.2f}", f"{c:.2f}"])
finally:
    csv_f.flush(); csv_f.close()
