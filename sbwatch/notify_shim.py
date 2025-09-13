from __future__ import annotations
import os, json, atexit, traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from importlib import import_module
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
FORWARD_PATH = os.getenv("FORWARD_ALERT_FN", "").strip()

COUNT = 0
FIRST_TS: Optional[str] = None
CONTRACT = os.getenv("CONTRACT", os.getenv("SYMBOL",""))
REPLAY_DAY = os.getenv("REPLAY_ET_DATE","")
SCHEMA = os.getenv("SCHEMA","ohlcv-1m")

def _post_discord(text: str) -> None:
    if not WEBHOOK:
        return
    # Discord content max ~2000 chars. We keep it short and chunk if needed.
    for chunk in [text[i:i+1800] for i in range(0, len(text), 1800)] or ["(empty)"]:
        data = json.dumps({"content": chunk}).encode("utf-8")
        req = Request(WEBHOOK, data=data, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as resp:
                # 204 No Content is success
                pass
        except (HTTPError, URLError):
            # Do not crash the pipeline on Discord errors
            traceback.print_exc()

def _fmt_event(evt: Dict[str, Any]) -> str:
    # Try common fields, fallback to the dict text
    etype = str(evt.get("type") or evt.get("label") or "ALERT")
    ts = evt.get("ts") or evt.get("time") or evt.get("timestamp")
    price = evt.get("price") or evt.get("px") or evt.get("close")
    extra = evt.get("note") or evt.get("notes") or ""
    base = f"🔔 {etype}"
    if ts: base += f" @ {ts}"
    if price is not None: base += f" | {price}"
    if extra: base += f" — {extra}"
    return base

def _maybe_import_forward():
    if not FORWARD_PATH:
        return None
    try:
        mod, func = FORWARD_PATH.rsplit(".", 1)
        return getattr(import_module(mod), func)
    except Exception:
        traceback.print_exc()
        return None

# Send a "start" heartbeat when shim is imported (optional)
if os.getenv("REPLAY_START_NOTI", "1") == "1":
    _post_discord(f"▶️ SB Watchbot replay starting | day={REPLAY_DAY or '(auto)'} | contract={CONTRACT} | schema={SCHEMA}")

@atexit.register
def _summary():
    _post_discord(f"📊 SB Watchbot replay finished | day={REPLAY_DAY or '(auto)'} | contract={CONTRACT} | alerts={COUNT}")

_FORWARD = _maybe_import_forward()

def dispatch(event: Dict[str, Any]) -> None:
    global COUNT, FIRST_TS
    try:
        if FIRST_TS is None:
            FIRST_TS = str(event.get("ts") or event.get("time") or "")
        COUNT += 1
        # Send to Discord
        _post_discord(_fmt_event(event))
        # Forward to the original alert dispatcher if configured
        if _FORWARD:
            _FORWARD(event)
    except Exception:
        traceback.print_exc()
