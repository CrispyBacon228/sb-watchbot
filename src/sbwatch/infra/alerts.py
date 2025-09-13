import json
import httpx
from typing import Dict, Any, Optional

class AlertSink:
    def publish(self, payload: Dict[str, Any]) -> None:
        raise NotImplementedError

class DiscordSink(AlertSink):
    def __init__(self, webhook_url: str, timeout: float = 10.0, verbose: bool = False) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.verbose = verbose

    def publish(self, payload: Dict[str, Any]) -> None:
        if not self.webhook_url:
            raise ValueError("Discord webhook URL is empty")

        content: Optional[str] = payload.pop("content", None)
        if content is None:
            content = f"```json\n{json.dumps(payload, indent=2)}\n```"

        try:
            resp = httpx.post(self.webhook_url, json={"content": content}, timeout=self.timeout)
        except Exception as e:
            raise RuntimeError(f"Discord request failed: {e!r}") from e

        if self.verbose:
            print(f"[discord] status={resp.status_code} body={resp.text[:200]}")

        if resp.status_code not in (200, 204):
            raise RuntimeError(
                f"Discord webhook error: status={resp.status_code} body={resp.text[:500]}"
            )
