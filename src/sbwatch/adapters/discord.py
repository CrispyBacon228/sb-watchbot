from __future__ import annotations
import os, json, time
import requests
from typing import Optional

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def send_discord(content: str, username: str = "SB Watchbot", embeds: Optional[list] = None) -> bool:
    """Post a message to Discord webhook. Returns True on success."""
    if not WEBHOOK:
        print("[discord] No DISCORD_WEBHOOK_URL set; skipping send.")
        return False
    payload = {"content": content}
    if username:
        payload["username"] = username
    if embeds:
        payload["embeds"] = embeds
    try:
        r = requests.post(WEBHOOK, json=payload, timeout=10)
        if r.status_code // 100 == 2:
            return True
        print(f"[discord] Non-2xx: {r.status_code} -> {r.text[:200]}")
    except Exception as e:
        print(f"[discord] Exception: {e}")
    return False
