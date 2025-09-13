from __future__ import annotations
import json, os
from typing import Dict, Any
from loguru import logger as log
from datetime import datetime
from dateutil import tz

NY = tz.gettz("America/New_York")

def _today_key(dt: datetime) -> str: return dt.astimezone(NY).strftime("%Y-%m-%d")

class Levels:
    def __init__(self, path: str):
        self.path = path; self.data: Dict[str, Any] = {}; self.mtime = 0; self._load()

    def _load(self):
        if not os.path.exists(self.path):
            log.warning(f"levels file not found: {self.path}"); self.data = {}; self.mtime = 0; return
        st = os.stat(self.path)
        if st.st_mtime == self.mtime: return
        try:
            with open(self.path, "r") as f: self.data = json.load(f)
            self.mtime = st.st_mtime; log.info(f"Loaded levels from {self.path}")
        except Exception as e:
            log.error(f"Failed to load levels: {e}"); self.data = {}

    def get_for_today(self, now_dt: datetime) -> Dict[str, Any] | None:
        self._load(); return self.data.get(_today_key(now_dt))

    def example_today(self, now_dt: datetime) -> Dict[str, Any]:
        return {"asia":{"high":0,"low":0,"start":"18:00","end":"00:00"},
                "london":{"high":0,"low":0,"start":"02:00","end":"05:00"},
                "prev_day":{"high":0,"low":0}}
