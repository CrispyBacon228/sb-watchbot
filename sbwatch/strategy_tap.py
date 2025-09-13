from __future__ import annotations
import os, traceback
from importlib import import_module
from typing import Any, Dict, Iterable

# import the real strategy from env (default to your known path)
FORWARD_PATH = os.getenv("FORWARD_STRATEGY_FN", "sbwatch.strategy.process_bar")
WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

def _load_callable(path: str):
    mod, fn = path.rsplit(".", 1)
    return getattr(import_module(mod), fn)

def _post_discord(msg: str) -> None:
    if not WEBHOOK:
        return
    try:
        import json
        from urllib.request import Request, urlopen
        req = Request(WEBHOOK, json.dumps({"content": msg}).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=5) as _:
            pass
    except Exception:
        traceback.print_exc()

_forward = _load_callable(FORWARD_PATH)

def process_bar(row, **kwargs) -> Iterable[Dict[str, Any]] | None:
    """Wrapper around your real strategy that logs/forwards any events."""
    try:
        events = _forward(row, **kwargs)
        if events:
            # send one-line summary to Discord for visibility
            # (kept short to avoid 2000 char limit)
            _post_discord(f"🔔 Strategy emitted {len(events)} event(s) at {kwargs.get('contract','?')}")
        return events
    except Exception:
        traceback.print_exc()
        # surface failure to Discord so we know strategy errored
        _post_discord("❌ Strategy raised an exception; check logs.")
        return None
