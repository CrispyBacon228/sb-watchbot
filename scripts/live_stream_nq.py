import os
DIVISOR = float(os.getenv("SB_DIV", "1000000000"))  # default 1e9
DIVISOR = float(os.getenv("SB_DIV","1000000000"))  # 1e9 by default
import os
import os, time, pathlib, traceback
import pandas as pd
import databento

CSV_PATH = os.environ.get("LIVE_CSV", "/opt/sb-watchbot/live/nq_1m.csv")
SYM = os.environ.get("SYM", "NQZ5")
API_KEY = os.environ["DATABENTO_API_KEY"]
LOG = "/opt/sb-watchbot/out/live_stream.log"

pathlib.Path(os.path.dirname(CSV_PATH)).mkdir(parents=True, exist_ok=True)
pathlib.Path(os.path.dirname(LOG)).mkdir(parents=True, exist_ok=True)

def log(*a):
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    with open(LOG, "a") as f:
        f.write(ts + " | " + " ".join(map(str, a)) + "\n")

# choose a divisor so final price is in a sane futures range (1k..100k)
CANDIDATE_DIVISORS = [1e12, 1e11, 1e10, 1e9, 1e8, 1e7, 1e6, 1e5, 1e4, 100, 1]
def pick_divisor(v: float) -> float:
    v = abs(float(v))
    for d in CANDIDATE_DIVISORS:
        s = v / d
        if 1_000 <= s <= 100_000:
            return d
    return 1.0

def pkt_to_df(pkt) -> pd.DataFrame:
    to_df = getattr(pkt, "to_df", None)
    if callable(to_df):
        try:
            df = to_df()
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception:
            pass
    cols = ["open","high","low","close","volume"]
    vals = {c:getattr(pkt,c,None) for c in cols}
    ts = getattr(pkt, "ts_event", None)
    if ts is None:
        hd = getattr(pkt, "hd", None)
        ts = getattr(hd, "ts_event", None) if hd else None
    if ts and all(v is not None for v in vals.values()):
        vals["ts_event"] = ts
        return pd.DataFrame([vals])
    return pd.DataFrame()

def append_rows(df: pd.DataFrame):
    # scale prices automatically using the last 'close'
    scale_source = None
    for c in ["close","open","high","low"]:
        if c in df.columns:
            scale_source = df[c].iloc[-1]
            break
    d = DIVISOR if scale_source is not None else 1.0
    for c in ["open","high","low","close"]:
        if c in df.columns:
            df[c] = df[c].astype(float)/DIVISOR

    # timestamp → ISO8601 UTC
    if "timestamp" not in df.columns:
        if "ts_event" in df.columns:
            ts = pd.to_datetime(df["ts_event"], unit="ns", utc=True)
            df = df.assign(timestamp=ts.dt.strftime("%Y-%m-%dT%H:%M:%S%z"))
        elif isinstance(df.index, pd.DatetimeIndex):
            ts = df.index.tz_convert("UTC") if df.index.tz is not None else df.index.tz_localize("UTC")
            df = df.reset_index().rename(columns={"index":"timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    out_cols = [c for c in ["timestamp","open","high","low","close","volume"] if c in df.columns]
    if not out_cols:
        log("WARN no ohlcv columns", list(df.columns)); return
    header = not os.path.exists(CSV_PATH)
    df[out_cols].to_csv(CSV_PATH, mode="a", index=False, header=header)
    log("APPEND", len(df), "rows", "div=", d, "last_ts=", df["timestamp"].iloc[-1])

def main():
    log(f"Starting live stream; dataset=GLBX.MDP3 schema=ohlcv-1m sym={SYM} stype_in=raw_symbol")
    client = databento.Live(API_KEY)
    client.subscribe("GLBX.MDP3","ohlcv-1m",symbols=[SYM],stype_in="raw_symbol")
    for pkt in client:
        try:
            df = pkt_to_df(pkt)
            if not df.empty:
                append_rows(df)
        except Exception:
            log("ERROR", traceback.format_exc()); time.sleep(0.3)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
