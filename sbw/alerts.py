from __future__ import annotations
import requests, time
from loguru import logger as log

class Discord:
    def __init__(self, webhook: str): self.url = webhook.strip()
    def post(self, content: str):
        if not self.url:
            log.warning(f"(NO DISCORD WEBHOOK) Would post:\n{content}"); return
        for attempt in range(5):
            r = requests.post(self.url, json={"content": content}, timeout=10)
            if r.status_code in (200,204): return
            if r.status_code in (429,500,502,503,504):
                time.sleep(1.5*(attempt+1)); continue
            r.raise_for_status()
