from __future__ import annotations
import typer
from typing import Optional
from sbwatch.adapters.discord import send_discord
from sbwatch.util.alerts import append_alert

app = typer.Typer(help="Notification helpers")

@app.command("send")
def send(
    msg: Optional[str] = typer.Argument(None, help="Message (positional)"),
    msg_opt: Optional[str] = typer.Option(None, "--msg", "-m", help="Message (option)"),
):
    text = msg_opt if msg_opt is not None else msg
    if not text:
        raise typer.BadParameter("Provide a message (positional or --msg)")
    send_discord(text)

@app.command("test-discord")
def test_discord():
    send_discord("✅ sb-watchbot: Discord test ping")

@app.command("test-log")
def test_log():
    from os import getenv
    append_alert("TEST_ALERT", getenv("FRONT_SYMBOL","NQ?"), 12345.0, 12300.0)
    typer.echo("Wrote test alert to today's live CSV")
