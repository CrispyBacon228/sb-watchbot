"""
Thin compatibility shim for Databento Live client.

Some versions expose Live at `databento.live.Live`, others at
`databento.live.client.Live`. We try both so the rest of the code can do:

    from sbw.db_live import Live
"""
from __future__ import annotations

try:
    # Newer layout (preferred)
    from databento.live import Live  # type: ignore[attr-defined]
except Exception:
    # Fallback: older (or alternate) layout
    from databento.live.client import Live  # type: ignore

__all__ = ["Live"]
