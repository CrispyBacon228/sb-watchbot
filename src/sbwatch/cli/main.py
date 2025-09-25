from __future__ import annotations
import typer
from sbwatch.cli.levels_cmd import app as levels_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(levels_app, name="levels")

if __name__ == "__main__":
    app()
