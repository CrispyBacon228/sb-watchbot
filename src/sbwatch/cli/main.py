from __future__ import annotations
import sbwatch._bootstrap_env
import typer
from sbwatch.cli import levels_cmd, live_cmd, notify_cmd, replay_cmd, status_cmd
from sbwatch.cli.ict_cmd import app as ict_app
from sbwatch.cli.ict_explain_cmd import app as ict_explain_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(levels_cmd.app,  name="levels")
app.add_typer(live_cmd.app,    name="live")
app.add_typer(notify_cmd.app,  name="notify")
app.add_typer(replay_cmd.app,  name="replay")
app.add_typer(status_cmd.app,  name="status")
app.add_typer(ict_app,         name="ict")
app.add_typer(ict_explain_app, name="ict-explain")

if __name__ == "__main__":
    app()
