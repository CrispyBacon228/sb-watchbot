from __future__ import annotations
import typer
from typing import Optional
from sbwatch.engine.replay import run_replay

app = typer.Typer(help="Replay a past day and export alerts to CSV.")

@app.command("run")
def run(
    date: str = typer.Option(..., "--date", "-d", help="ET date YYYY-MM-DD"),
    csv: Optional[str] = typer.Option(None, "--csv", help="Optional local CSV to use"),
    out: str = typer.Option("./out", "--out", help="Output directory"),
    wick_only: bool = typer.Option(True, "--wick-only/--no-wick-only", help="Only wick rejects or include crosses too"),
):
    path = run_replay(date_et=date, out_dir=out, csv_path=csv, wick_only=wick_only)
    typer.echo(f"Wrote → {path}")
