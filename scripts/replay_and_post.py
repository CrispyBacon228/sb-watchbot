#!/usr/bin/env python
import os, sys, json, subprocess, argparse
from datetime import datetime, date
try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    from backports.zoneinfo import ZoneInfo  # type: ignore

ET = ZoneInfo("America/New_York")

def is_weekend(d: date) -> bool:
    # Monday=0 ... Sunday=6
    return d.weekday() >= 5

def post_discord(msg: str) -> None:
    """Post a simple text message to DISCORD_WEBHOOK. Adds ?wait=true and uses sane headers."""
    wh = (os.environ.get("DISCORD_WEBHOOK") or "").strip()
    if not wh:
        print("[INFO] DISCORD_WEBHOOK not set; skipping Discord post.")
        return

    # Append wait=true safely
    from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qsl
    import urllib.request

    parts = urlsplit(wh)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.setdefault("wait", "true")
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))

    data = json.dumps({"content": msg}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SBWatchbot/1.0 (+https://github.com/CrispyBacon228/sb-watchbot)",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            print(f"[INFO] Discord HTTP {code}")
    except Exception as e:
        print(f"[WARN] Discord post failed: {e}")

def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD in ET (default: today ET)")
    args = ap.parse_args(argv)

    if args.date:
        dt = datetime.fromisoformat(args.date).date()
    else:
        dt = datetime.now(ET).date()

    if is_weekend(dt):
        msg = f"SB Watchbot: Weekend ({dt.isoformat()} ET) — skipping replay/post."
        print(msg)
        post_discord(msg)
        return 0

    date_et = dt.isoformat()
    print(f"[INFO] Running replay+post for {date_et} (ET).")
    try:
        subprocess.check_call(["bash", "./scripts/replay_day.sh", date_et], cwd=os.getcwd())
        post_discord(f"SB Watchbot: Replay complete for {date_et} ET.")
    except subprocess.CalledProcessError as e:
        post_discord(f"SB Watchbot: Replay failed for {date_et} ET (exit {e.returncode}).")
        return e.returncode
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
