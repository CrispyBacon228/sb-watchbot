from __future__ import annotations
import os, requests

def post_discord(text: str) -> bool:
    """
    Sends a simple text message to a Discord webhook.
    Reads DISCORD_WEBHOOK from environment. Returns True on success.
    """
    url = os.getenv("DISCORD_WEBHOOK")
    if not url or not text:
        return False
    try:
        r = requests.post(url, json={"content": text}, timeout=8)
        return r.ok
    except Exception:
        return False
