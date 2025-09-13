import os, json, urllib.request
url = os.environ.get("DISCORD_WEBHOOK_URL")
if not url:
    print("No DISCORD_WEBHOOK_URL set"); raise SystemExit(2)

def post(obj):
    data = json.dumps({"content": "```json\n"+json.dumps(obj, indent=2)+"\n```"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        print("POST", obj.get("type"), "->", resp.status)

post({"type":"REPLAY_START","contract":os.environ.get("FRONT_SYMBOL","NQZ5"),
      "date":os.environ.get("REPLAY_ET_DATE","(unset)"), "schema":os.environ.get("DB_SCHEMA","ohlcv-1m")})
post({"type":"REPLAY_DATA","contract":os.environ.get("FRONT_SYMBOL","NQZ5"),
      "date":os.environ.get("REPLAY_ET_DATE","(unset)"), "bars": 90})
post({"type":"REPLAY_DONE","contract":os.environ.get("FRONT_SYMBOL","NQZ5"),
      "date":os.environ.get("REPLAY_ET_DATE","(unset)"), "alerts_sent": 0})
print("✅ replay_alerts_smoke completed")
