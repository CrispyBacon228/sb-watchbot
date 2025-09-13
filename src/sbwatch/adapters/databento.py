from __future__ import annotations
from typing import Iterable, Dict, Any

class DataBentoSource:
    def __init__(self, api_key: str | None, dataset: str, schema: str, symbol: str) -> None:
        self.api_key = api_key
        self.dataset = dataset
        self.schema = schema
        self.symbol = symbol

    def replay(self, date: str) -> Iterable[Dict[str, Any]]:
        # TODO: replace with real historical fetch
        return []

    def stream(self) -> Iterable[Dict[str, Any]]:
        # TODO: replace with real live stream
        return []
