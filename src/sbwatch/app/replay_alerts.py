"""
Legacy shim for backward compatibility.

Old calls:
    python -m sbwatch.app.replay_alerts --csv path.csv [--date YYYY-MM-DD] [--out ./out] [--no-wick-only]

This forwards to:
    python -m sbwatch.cli.main replay run ...
"""
import argparse
import subprocess
import sys
from datetime import datetime, timezone
import os

def today_et():
    # If tz isn't available on system, fall back to UTC date
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        return datetime.now(et).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=None, help="Optional CSV to use")
    p.add_argument("--date", default=None, help="ET date YYYY-MM-DD")
    p.add_argument("--out", default="./out", help="Output directory (CSV)")
    # legacy flags that some scripts passed; keep but ignore/forward sanely
    p.add_argument("--speed", default=None)       # ignored
    p.add_argument("--quiet", action="store_true")# ignored
    # allow either form to be passed through
    p.add_argument("--no-wick-only", dest="no_wick_only", action="store_true", default=False)
    p.add_argument("--wick-only", dest="wick_only", action="store_true", default=False)

    args = p.parse_args()
    date_str = args.date or os.environ.get("DATE_ET") or today_et()

    cmd = [
        sys.executable, "-m", "sbwatch.cli.main",
        "replay", "run",
        "--date", date_str,
        "--out", args.out,
    ]
    if args.csv:
        cmd += ["--csv", args.csv]
    if args.no_wick_only:
        cmd += ["--no-wick-only"]

    # Ensure out dir exists
    os.makedirs(args.out, exist_ok=True)

    # Call through to the new CLI
    subprocess.check_call(cmd)

if __name__ == "__main__":
    main()
