import os, sys, subprocess, json, datetime
from zoneinfo import ZoneInfo
from urllib import request

NY=ZoneInfo("America/New_York")
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK:
    print("DISCORD_WEBHOOK not set", file=sys.stderr); sys.exit(1)

# Today in ET
now_et = datetime.datetime.now(tz=NY)
date_str = now_et.strftime("%Y-%m-%d")

# 1) generate replay csv
subprocess.run(["bash","./scripts/replay_day.sh", date_str], check=True)

csv = f"out/replay_{date_str}.csv"
# 2) run replay and capture alert lines only (fast)
proc = subprocess.run(
    ["python","-m","sbwatch.app.replay_alerts","--csv",csv,"--speed","0"],
    capture_output=True, text=True, check=True
)
alerts = [ln for ln in proc.stdout.splitlines() if ln.startswith("[ALERT]")]
if not alerts:
    body = f"🟪 11:10 ET — Replay {date_str}: no SB alerts."
else:
    sample = "\n".join(alerts[:10])
    more = "" if len(alerts)<=10 else f"\n(+{len(alerts)-10} more…)"
    body = f"🟪 11:10 ET — Replay {date_str}: {len(alerts)} alert(s).\n```\n{sample}\n```{more}"

data = json.dumps({"content": body}).encode("utf-8")
req  = request.Request(WEBHOOK, data=data, headers={"Content-Type":"application/json"})
request.urlopen(req, timeout=10)
print("posted")
