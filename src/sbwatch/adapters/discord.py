import httpx
from typing import Mapping, Any

class DiscordSink:
    def __init__(self, webhook_url: str, timeout: float = 10.0, verbose: bool = False) -> None:
        if not webhook_url or not webhook_url.startswith("http"):
            raise ValueError("Invalid Discord webhook URL")
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.verbose = verbose

    def publish(self, payload: Mapping[str, Any]) -> None:
        content = payload.get("content")
        if not content:
            raise ValueError("Discord payload missing 'content'")
        try:
            r = httpx.post(self.webhook_url, json={"content": content}, timeout=self.timeout)
        except Exception as e:
            raise RuntimeError(f"Discord request failed: {e!r}") from e
        if self.verbose:
            print(f"[discord] status={r.status_code} body={r.text[:200]}")
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Discord webhook error: {r.status_code} {r.text[:300]}")
