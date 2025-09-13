from __future__ import annotations
from typing import Iterable, Dict, Any, Optional
import datetime as dt
import re

import databento as db  # pip install -U databento
import pandas as pd

def _infer_stype(symbol: str) -> str:
    if "." in symbol and symbol.split(".")[-1] in {"FUT", "OPT"}:
        return "parent"        # e.g. NQ.FUT
    if re.search(r"[0-9]$", symbol):
        return "raw_symbol"    # e.g. NQU5
    return "parent"

def _ns_to_iso(ns: int) -> str:
    return dt.datetime.utcfromtimestamp(int(ns) / 1_000_000_000).strftime("%Y-%m-%dT%H:%M:%SZ")

class DataBentoSource:
    def __init__(self, api_key: Optional[str], dataset: str, schema: str, symbol: str):
        self.dataset = dataset
        self.schema = schema          # 'ohlcv-1m'
        self.symbol = symbol          # 'NQ.FUT' or 'NQU5'
        self.stype_in = _infer_stype(symbol)
        self.hclient = db.Historical(api_key)
        try:
            self.lclient = db.Live(api_key)   # optional; may not be entitled
        except Exception:
            self.lclient = None

    # ---- HISTORICAL (use DataFrame for reliability) ----
    def replay(self, start: str, end: str) -> Iterable[Dict[str, Any]]:
        data = self.hclient.timeseries.get_range(
            dataset=self.dataset,
            schema=self.schema,
            symbols=self.symbol,
            stype_in=self.stype_in,
            start=start,
            end=end,
        )
        df: pd.DataFrame = data.to_df()

        # ts_event may be a column or the index depending on SDK/data
        if "ts_event" in df.columns:
            ts_series = df["ts_event"]
        else:
            ts_series = df.index.to_series()

        for i, row in df.iterrows():
            ts_val = ts_series.iloc[i] if "ts_event" in df.columns else i
            ts_iso = _ns_to_iso(int(ts_val)) if isinstance(ts_val, (int, float)) else str(ts_val)
            yield {
                "ts": ts_iso,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low":  float(row["low"]),
                "close":float(row["close"]),
                "volume": float(row["volume"]) if "volume" in df.columns else 0.0,
            }

    # ---- LIVE (best-effort for SDK 0.63.0; skip non-OHLCV) ----
    def stream(self) -> Iterable[Dict[str, Any]]:
        if self.lclient is None:
            raise RuntimeError("Databento Live client unavailable (no entitlement or SDK).")

        # subscribe (common shape in 0.63.0)
        if hasattr(self.lclient, "timeseries") and hasattr(self.lclient.timeseries, "subscribe"):
            self.lclient.timeseries.subscribe(
                dataset=self.dataset, schema=self.schema,
                symbols=self.symbol, stype_in=self.stype_in,
            )
            it = getattr(self.lclient, "start", None)
            if callable(it):
                for msg in it():
                    # Many messages are SystemMsg/Control — ignore those
                    if not hasattr(msg, "open"):   # not an OHLCV message
                        continue
                    ts = getattr(msg, "ts_event", None)
                    ts_iso = _ns_to_iso(int(ts)) if isinstance(ts, (int, float)) else str(ts)
                    yield {
                        "ts": ts_iso,
                        "open": float(msg.open),
                        "high": float(msg.high),
                        "low":  float(msg.low),
                        "close":float(msg.close),
                        "volume": float(getattr(msg, "volume", 0.0)),
                    }
                return

        # fallback pattern (older APIs)
        if hasattr(self.lclient, "subscribe"):
            self.lclient.subscribe(
                dataset=self.dataset, schema=self.schema,
                symbols=self.symbol, stype_in=self.stype_in,
            )
            event_iter = getattr(self.lclient, "events", None)
            if callable(event_iter):
                for msg in event_iter():
                    if not hasattr(msg, "open"):
                        continue
                    ts = getattr(msg, "ts_event", None)
                    ts_iso = _ns_to_iso(int(ts)) if isinstance(ts, (int, float)) else str(ts)
                    yield {
                        "ts": ts_iso,
                        "open": float(msg.open),
                        "high": float(msg.high),
                        "low":  float(msg.low),
                        "close":float(msg.close),
                        "volume": float(getattr(msg, "volume", 0.0)),
                    }
                return

        raise RuntimeError("Databento Live API signature not recognized in this SDK build.")
