import os, json
from typing import Dict, Any
from loguru import logger as log

class KVState:
    def __init__(self, path: str):
        self.path = path; self.data: Dict[str, Any] = {}; self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f: self.data = json.load(f)
            except Exception as e:
                log.warning(f"Failed to load state {self.path}: {e}"); self.data = {}
        else:
            self.data = {}

    def save(self):
        tmp = self.path + ".tmp"
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(tmp, "w") as f: json.dump(self.data, f)
        os.replace(tmp, self.path)

    def get(self, key, default=None): return self.data.get(key, default)
    def set(self, key, value): self.data[key] = value
