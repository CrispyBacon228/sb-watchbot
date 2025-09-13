from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict

@dataclass
class CooldownManager:
    per_level_seconds: int = 600
    global_seconds: int = 300
    _last_any: datetime | None = None
    _by_key: Dict[str, datetime] = field(default_factory=dict)

    def ok(self, key: str, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        # global
        if self._last_any and (now - self._last_any) < timedelta(seconds=self.global_seconds):
            return False
        # per-key
        last = self._by_key.get(key)
        if last and (now - last) < timedelta(seconds=self.per_level_seconds):
            return False
        return True

    def mark(self, key: str, when: datetime | None = None) -> None:
        when = when or datetime.utcnow()
        self._last_any = when
        self._by_key[key] = when
