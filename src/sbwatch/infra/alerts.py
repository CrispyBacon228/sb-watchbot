import json
import httpx
from typing import Dict, Any

class AlertSink:
    def publish(self, payload: Dict[str, Any]) -> None:
        raise NotImplementedError

class DiscordSink(AlertSink):
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def publish(self, payload: Dict[str, Any]) -> None:
        # payload should already be a dict; we'll stringify for Discord content
        content = payload.pop("content", None)
        if content is None:
            content = f"```json\n{json.dumps(payload, indent=2)}\n```"
        data = {"content": content}
        # Optional: include embeds/extra fields later
        httpx.post(self.webhook_url, json=data, timeout=10.0)
