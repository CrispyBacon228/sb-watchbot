from __future__ import annotations
import typer
from typing import Optional
from sbwatch.adapters.discord import send_discord

app = typer.Typer(help="Send a one-off test message to Discord.")

@app.command("send")
def send(
    msg: Optional[str] = typer.Argument(None, help="Message (positional)"),
    msg_opt: Optional[str] = typer.Option(None, "--msg", "-m", help="Message (option)"),
):
    text = msg_opt if msg_opt is not None else msg
    if not text:
        raise typer.BadParameter("Provide a message as a positional argument or with --msg/-m")
    send_discord(text)
