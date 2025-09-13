from __future__ import annotations
from typing import Iterable, Dict, Any, Optional
import datetime as dt
import databento as db  # pip install databento

class DataBentoSource:
    def __init__(self, api_key: Optional[str], dataset: str, schema: str, symbol: str):
        self.dataset = dataset
        self.schema = schema
        self.symbol = symbol
        self.hclient = db.Historical(api_key)  # Historical client
        try:
            self.lclient = db.Live(api_key)    # Live client (optional)
        except Exception:
            self.lclient = None

    @staticmethod
    def _row_to_bar(row: Dict[str, Any]) -> Dict[str, Any]:
        o = float(row["open"]); h = float(row["high"])
        l = float(row["low"]);  c = float(row["close"])
        v = float(row.get("volume", 0.0))
        ts = row.get("ts_event") or row.get("ts")
        if isinstance(ts, (int, float)):  # ns -> ISO
            ts = dt.datetime.utcfromtimestamp(int(ts) / 1_000_000_000).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}

    def replay(self, start: str, end: str) -> Iterable[Dict[str, Any]]:
        data = self.hclient.timeseries.get_range(
            dataset=self.dataset,
            schema=self.schema,          # e.g. 'ohlcv-1m'
            symbols=self.symbol,         # e.g. 'NQU5' or parent symbology
            stype_in="parent",
            start=start,
            end=end,
        )
        out = []
        def _cb(ev):
            row = dict(ev)
            out.append(self._row_to_bar(row))
        data.replay(callback=_cb)
        for r in out:
            yield r

    def stream(self) -> Iterable[Dict[str, Any]]:
        if self.lclient is None:
            raise RuntimeError("Live client unavailable; set DATABENTO_API_KEY and ensure databento supports Live.")
        self.lclient.timeseries.subscribe(
            dataset=self.dataset, schema=self.schema, symbols=self.symbol, stype_in="parent",
        )
        for ev in self.lclient.start():
            row = dict(ev)
            yield self._row_to_bar(row)
