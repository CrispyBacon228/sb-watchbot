from __future__ import annotations
from datetime import datetime, timedelta

class Dedupe:
    def __init__(self, global_cooldown_min: int):
        self.gc = timedelta(minutes=global_cooldown_min)
        self.last_entry_at: datetime | None = None

    def allow_entry(self, now: datetime) -> bool:
        if not self.last_entry_at: self.last_entry_at = now; return True
        if now - self.last_entry_at >= self.gc: self.last_entry_at = now; return True
        return False
