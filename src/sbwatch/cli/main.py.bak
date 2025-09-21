from __future__ import annotations
import os, json
import typer
from sbwatch.core.levels import DayLevels

app = typer.Typer(help="sbwatch: AI trading alert system")

@app.command("check-env")
def check_env() -> None:
    keys = (
        "DATABENTO_API_KEY",
        "DB_DATASET",
        "DB_SCHEMA",
        "FRONT_SYMBOL",
        "PRICE_DIVISOR",
        "DISCORD_WEBHOOK_URL",
    )
    for k in keys:
        print(f"{k}={os.getenv(k,'')}")

@app.command("replay")
def replay(date: str) -> None:
    # placeholder; not needed for levels writing
    typer.echo(f"[replay] stub for {date}")

@app.command("build-levels")
def build_levels_cmd(date: str) -> None:
    """Write Asia/London session levels JSON (drop pdh/pdl)."""
    out = {
        "date": date,
        "asia_high": None,
        "asia_low": None,
        "london_high": None,
        "london_low": None,
    }
    import os, json
    os.makedirs("data", exist_ok=True)
    with open("data/levels.json", "w") as f:
        json.dump(out, f)
    print(f"[sbwatch] built levels {out}")

def main() -> None:
    app()

if __name__ == "__main__":
    main()
