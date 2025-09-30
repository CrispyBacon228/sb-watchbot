from __future__ import annotations
from sbwatch._bootstrap_env import *  # loads .env

import os, time
from datetime import datetime, timezone
import typer

from sbwatch.data.ohlcv import get_ohlcv_1m
from sbwatch.strategy.ict_sb import detect_signal_strict as detect_signal
from sbwatch.adapters.discord import send_discord

def main(
    symbol: str = typer.Option(os.getenv("SYMBOL","NQ"), help="Symbol, e.g., NQ"),
    poll: int = typer.Option(int(os.getenv("POLL_SECONDS", "5")), help="Poll seconds"),
):
    seen = set()
    typer.echo(f"[live] Starting for {symbol} (poll={poll}s)")
    while True:
        now = datetime.now(timezone.utc)
        df = get_ohlcv_1m(symbol, lookback_mins=600)
        if not df.empty and df["timestamp"].dtype.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

        sig = detect_signal(df, now)
        if sig:
            side, px = sig.side, sig.price
            key = f"{side}@{int(px)}:{now.strftime('%Y-%m-%dT%H:%M')}"
            if key not in seen:
                seen.add(key)
                msg = f"**{side}** signal at `{px:.2f}` — {symbol} — {now.isoformat()}"
                send_discord(msg)
                typer.echo(f"[live] ALERT {msg}")
        time.sleep(poll)

if __name__ == "__main__":
    typer.run(main)
