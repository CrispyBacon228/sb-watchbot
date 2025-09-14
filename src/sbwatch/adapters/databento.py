from __future__ import annotations
from typing import Iterable, Dict, Any, Optional
import datetime as dt
import re
import databento as db

def _infer_stype(symbol: str) -> str:
    if "." in symbol and symbol.split(".")[-1] in {"FUT", "OPT"}:
        return "parent"
    if re.search(r"[0-9]$", symbol):
        return "raw_symbol"
    return "parent"

def _ns_to_iso(ns: int) -> str:
    return dt.datetime.utcfromtimestamp(int(ns) / 1_000_000_000).strftime("%Y-%m-%dT%H:%M:%SZ")

class DataBentoSource:
    def __init__(self, api_key: Optional[str], dataset: str, schema: str, symbol: str):
        self.dataset = dataset
        self.schema = schema
        self.symbol = symbol
        self.stype_in = _infer_stype(symbol)
        self.hclient = db.Historical(api_key)
        try:
            self.lclient = db.Live(api_key)
        except Exception:
            self.lclient = None

    # -------- HISTORICAL --------
    def replay(self, start: str, end: str) -> Iterable[Dict[str, Any]]:
        data = self.hclient.timeseries.get_range(
            dataset=self.dataset, schema=self.schema,
            symbols=self.symbol, stype_in=self.stype_in,
            start=start, end=end,
        )
        df = data.to_df()
        ts_col = "ts_event" if "ts_event" in df.columns else None
        for i, row in df.iterrows():
            ts_val = (int(df[ts_col].iloc[i]) if ts_col else int(i)) if isinstance((df[ts_col].iloc[i] if ts_col else i), (int,float)) else (df[ts_col].iloc[i] if ts_col else i)
            ts_iso = _ns_to_iso(ts_val) if isinstance(ts_val, (int,float)) else str(ts_val)
            yield {
                "ts": ts_iso,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low":  float(row["low"]),
                "close":float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            }

    # -------- LIVE --------
    def _row_to_bar_from_attrs(self, msg: Any) -> Dict[str, Any]:
        if not all(hasattr(msg, k) for k in ("open","high","low","close")):
            raise TypeError("Not an OHLCV message")
        ts = getattr(msg, "ts_event", getattr(msg, "ts", None))
        ts_iso = _ns_to_iso(int(ts)) if isinstance(ts, (int,float)) else str(ts)
        return {
            "ts": ts_iso,
            "open": float(msg.open),
            "high": float(msg.high),
            "low":  float(msg.low),
            "close":float(msg.close),
            "volume": float(getattr(msg, "volume", 0.0)),
        }

    def stream(self) -> Iterable[Dict[str, Any]]:
        if self.lclient is None:
            raise RuntimeError("Databento Live unavailable. Historical works; check API key/plan or upgrade 'databento'.")

        lc = self.lclient

        # subscribe via whatever exists
        if hasattr(lc, "timeseries") and hasattr(lc.timeseries, "subscribe"):
            lc.timeseries.subscribe(dataset=self.dataset, schema=self.schema,
                                    symbols=self.symbol, stype_in=self.stype_in)
        elif hasattr(lc, "subscribe"):
            lc.subscribe(dataset=self.dataset, schema=self.schema,
                         symbols=self.symbol, stype_in=self.stype_in)

        def is_ohlcv(x: Any) -> bool:
            return all(hasattr(x, k) for k in ("open","high","low","close"))

        # A) Prefer ITERATOR FIRST (your SDK wants this before any start())
        try:
            for msg in lc:
                if not is_ohlcv(msg): 
                    continue
                yield self._row_to_bar_from_attrs(msg)
            return
        except Exception:
            pass  # fall back to other surfaces

        # B) events()
        if hasattr(lc, "events") and callable(lc.events):
            for msg in lc.events():
                if not is_ohlcv(msg): 
                    continue
                yield self._row_to_bar_from_attrs(msg)
            return

        # C) timeseries.stream()
        ts = getattr(lc, "timeseries", None)
        if ts is not None and hasattr(ts, "stream") and callable(ts.stream):
            for msg in ts.stream():
                if not is_ohlcv(msg): 
                    continue
                yield self._row_to_bar_from_attrs(msg)
            return

        # D) start() ONLY IF IT RETURNS AN ITERABLE (some builds return None)
        if hasattr(lc, "start") and callable(lc.start):
            try:
                res = lc.start()
            except Exception:
                res = None
            if res is not None:
                for msg in res:
                    if not is_ohlcv(msg):
                        continue
                    yield self._row_to_bar_from_attrs(msg)
                return
            # if None, last resort below

        # E) recv()/next() loop (very old/custom)
        for meth in ("recv", "next"):
            fn = getattr(lc, meth, None)
            if callable(fn):
                while True:
                    msg = fn()
                    if not is_ohlcv(msg):
                        continue
                    yield self._row_to_bar_from_attrs(msg)

        raise RuntimeError("Databento Live API not found; tried iterator, events(), timeseries.stream(), start(), recv/next.")
