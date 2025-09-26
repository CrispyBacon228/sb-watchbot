from __future__ import annotations
import os, requests
from loguru import logger

def _mask(url: str, keep: int = 10) -> str:
    if not url: return ""
    if len(url) <= keep: return url
    return url[:keep] + "..."

def send_discord(content: str) -> None:
    """
    Send a simple Discord message.
    - Reads DISCORD_WEBHOOK_URL at call time (no stale cache).
    - If missing or malformed, logs a warning and returns without error.
    """
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url or "REPLACE_WITH_YOUR_DISCORD_WEBHOOK" in url or not url.startswith(("http://","https://")):
        logger.warning("Discord webhook not set or invalid; skipping send.")
        return
    try:
        r = requests.post(url, json={"content": content}, timeout=10)
        if r.status_code >= 300:
            logger.error("Discord POST failed {}: {}", r.status_code, r.text[:200])
        else:
            logger.info("Discord OK → {}", _mask(url))
    except Exception as e:
        logger.exception("Discord send failed: {}", e)
