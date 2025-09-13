#!/usr/bin/env python3
from __future__ import annotations
import os
from databento import Historical

def get_historical(api_key: str | None = None) -> Historical:
    """
    Returns a Historical client compatible with different SDK signatures.
    Tries positional first, falls back to env-only ctor.
    """
    key = api_key or os.getenv("DATABENTO_API_KEY") or None
    # Try positional key (works on older/newer versions)
    try:
        return Historical(key) if key else Historical()
    except TypeError:
        # Fallback: some builds only accept env
        return Historical()
