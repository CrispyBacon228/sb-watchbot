from __future__ import annotations
import os
from datetime import datetime, timezone
import typer
from sbwatch.adapters.discord import send_discord
from sbwatch.data.ohlcv import get_ohlcv_1m

app = typer.Typer(help="Preflight sanity checks")

@app.command()
def discord():
    ok = send_discord(f"Preflight OK — {datetime.now(timezone.utc).isoformat()}")
    raise SystemExit(0 if ok else 1)

@app.command()
def data(symbol: str = os.getenv("SYMBOL","NQ")):
    df = get_ohlcv_1m(symbol, lookback_mins=90)
    typer.echo(df.tail(3).to_string(index=False))
    raise SystemExit(0 if len(df) > 0 else 1)

if __name__ == "__main__":
    app()
