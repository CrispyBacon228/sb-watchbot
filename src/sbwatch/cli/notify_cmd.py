from __future__ import annotations
import typer
from typing import Optional
from sbwatch.adapters.discord import send_discord
from sbwatch.engine.live import _log_alert  # uses same CSV path as live

app = typer.Typer(help="Notification helpers (Discord + local alert log).")

@app.command("send")
def send(
    msg: Optional[str] = typer.Argument(None, help="Message (positional)"),
    msg_opt: Optional[str] = typer.Option(None, "--msg", "-m", help="Message (option)"),
):
    text = msg_opt if msg_opt is not None else msg
    if not text:
        raise typer.BadParameter("Provide a message as positional or with --msg/-m")
    send_discord(text)

@app.command("test-discord")
def test_discord():
    """Send a test message to your Discord webhook."""
    send_discord("✅ sb-watchbot: Discord test ping")

@app.command("test-log")
def test_log():
    """Write a test alert row to the live alerts CSV."""
    _log_alert("TEST_ALERT", 12345.0, 12300.0)
    typer.echo("Wrote test alert to alerts_live.csv")
