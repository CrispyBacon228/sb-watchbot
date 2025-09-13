#!/usr/bin/env python3
"""
Posts a 9:00 AM ET 'Levels Report' to Discord for today's ET date,
reading /opt/sb-watchbot/data/levels.json.

Depends on:
- DISCORD_WEBHOOK_URL in /opt/sb-watchbot/.env
- Optional FRONT_SYMBOL in .env (shown in header)
- levels.json already populated (e.g., by sb-watchbot-levels.service at 08:59 ET)
"""
import os, json, sys
from datetime import datetime
from dateutil import tz
import requests

LEVELS_PATH = "/opt/sb-watchbot/data/levels.json"
NY = tz.gettz("America/New_York")

def today_key() -> str:
    return datetime.now(tz=NY).strftime("%Y-%m-%d")

def load_levels_for_today():
    if not os.path.exists(LEVELS_PATH):
        raise FileNotFoundError(f"levels file not found at {LEVELS_PATH}")
    with open(LEVELS_PATH, "r") as f:
        data = json.load(f) or {}
    key = today_key()
    return key, data.get(key)

def fmt(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)

def build_report(today, lv):
    # Expecting structure:
    # { "asia": {"high":..,"low":..}, "london": {"high":..,"low":..}, "prev_day": {"high":..,"low":..} }
    lines = []
    lines.append(f"**SB Watchbot — Levels Report** ({today})")
    front = os.getenv("FRONT_SYMBOL", "").strip()
    if front:
        lines.append(f"_Contract_: `{front}`")
    lines.append("")
    if "asia" in lv:
        lines.append(f"**Asia**   H/L: `{fmt(lv['asia']['high'])}` / `{fmt(lv['asia']['low'])}`  (18:00–00:00 ET)")
    if "london" in lv:
        lines.append(f"**London** H/L: `{fmt(lv['london']['high'])}` / `{fmt(lv['london']['low'])}`  (02:00–05:00 ET)")
    if "prev_day" in lv:
        lines.append(f"**Prev Day** H/L: `{fmt(lv['prev_day']['high'])}` / `{fmt(lv['prev_day']['low'])}`  (09:30–16:00 ET)")
    lines.append("")
    lines.append("_Heads up_: Trade alerts 09:30–10:00, SB entries 10:00–11:00, sweep info after London→10:00; **no alerts after 11:00**.")
    return "\n".join(lines)

def post_discord(msg: str):
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set")
    r = requests.post(url, json={"content": msg}, timeout=10)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"Discord post failed: {r.status_code} {r.text}")

def main():
    try:
        key, lv = load_levels_for_today()
        if not lv:
            post_discord(f"⚠️ SB Watchbot — No levels found for **{key}** in `{LEVELS_PATH}`. "
                         f"Builder may have failed. You can seed manually then rerun.")
            print("No levels for today; posted warning.")
            return 1
        msg = build_report(key, lv)
        post_discord(msg)
        print("Posted levels report.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
