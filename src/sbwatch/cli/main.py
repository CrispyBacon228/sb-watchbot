from __future__ import annotations
import sbwatch._bootstrap_env  # auto-load .env
import typer
from sbwatch.cli import levels_cmd, live_cmd, notify_cmd, replay_cmd

app = typer.Typer(no_args_is_help=True)
app.add_typer(levels_cmd.app, name="levels")
app.add_typer(live_cmd.app,   name="live")
app.add_typer(notify_cmd.app, name="notify")
app.add_typer(replay_cmd.app, name="replay")

if __name__ == "__main__":
    app()
