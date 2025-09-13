import typer
from sbwatch.infra.settings import settings
from sbwatch.infra.alerts import DiscordSink
from sbwatch.core.signals import DisplacementEvent, format_trade_message

app = typer.Typer(help="sbwatch: AI trading alert system")

@app.command()
def check_env():
    """Quick sanity check that env is wired."""
    typer.echo("DB_DATASET=" + settings.DB_DATASET)
    typer.echo("DB_SCHEMA=" + settings.DB_SCHEMA)
    typer.echo("FRONT_SYMBOL=" + settings.FRONT_SYMBOL)
    typer.echo("PRICE_DIVISOR=" + str(settings.PRICE_DIVISOR))
    typer.echo("Discord webhook present: " + str(bool(settings.DISCORD_WEBHOOK_URL)))

@app.command()
def send_test_alert():
    """Send a test alert to Discord to verify connectivity."""
    sink = DiscordSink(settings.DISCORD_WEBHOOK_URL)
    evt = DisplacementEvent(
        direction="SHORT",
        entry=23661.75,
        stop=23690.50,
        tp1=23463.75,
        tp2=23266.50,
        r_multiple=2.0,
        basis="London High"
    )
    content = format_trade_message(evt)
    sink.publish({"content": content})

@app.command()
def replay(date: str):
    """
    Run the replay pipeline for YYYY-MM-DD (stub).
    Plug your existing replay logic here, using settings + sinks.
    """
    typer.echo(f"Running replay for {date} with dataset={settings.DB_DATASET}, schema={settings.DB_SCHEMA}")
    # TODO: import your historical fetch, levels build, detection, and publish alerts via DiscordSink

@app.command()
def live():
    """
    Run live pipeline (stub).
    Plug your streaming/loop logic here.
    """
    typer.echo("Starting live alerts...")
    # TODO: connect to your live feed, detect setups, publish via DiscordSink

if __name__ == "__main__":
    app()
