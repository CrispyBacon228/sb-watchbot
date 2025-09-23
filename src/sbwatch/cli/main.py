from sbwatch.core.engine import SBEngine, SBParams
from sbwatch.app import load_levels_json
import typer, os
from dotenv import load_dotenv
from sbwatch.app import run_replay

load_dotenv(dotenv_path=".env")

from typing import Optional

app = typer.Typer(help="sbwatch: AI trading alert system")

@app.command()
def check_env():
    for k in ["DATABENTO_API_KEY","DB_DATASET","DB_SCHEMA","FRONT_SYMBOL","PRICE_DIVISOR","DISCORD_WEBHOOK_URL"]:
        v = os.getenv(k, "")
        if k == "DATABENTO_API_KEY" and v: v = v[:7] + "…"
        print(f"{k}={v if v else '(unset)'}")

@app.command()
def live(verbose: bool = typer.Option(False, "--verbose", "-v")):
    run_live(verbose=verbose)

@app.command()
def replay(date: str = typer.Argument(..., help="YYYY-MM-DD"),
           verbose: bool = typer.Option(False, "--verbose", "-v")):
    run_replay(date=date, verbose=verbose)

@app.command("build-levels")
def build_levels_cmd(date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD (optional)")):
    build_levels(date=date)

@app.command("send-test-alert")
def send_test_alert(verbose: bool = typer.Option(False, "--verbose", "-v")):
    from sbwatch.adapters.discord import DiscordSink
    wh = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not wh: raise SystemExit("DISCORD_WEBHOOK_URL not set")
    DiscordSink(wh, verbose=verbose).publish({"content":"✅ sbwatch test alert"})

# --- entrypoint required by the console script -------------------------------
def main() -> None:
    # Exported so `from sbwatch.cli.main import main; main()` works
    # (what venv/bin/sbwatch does).
    app()

# keep it runnable via `python -m sbwatch.cli.main`
if __name__ == "__main__":
    main()# --- FIX: import the actual build_levels function ---
from sbwatch.app import build_levels
