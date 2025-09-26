from __future__ import annotations
import typer
from sbwatch.engine.live import run_live

app = typer.Typer(help="Run live watcher and send Discord alerts.")

@app.command("run")
def run():
    run_live()
