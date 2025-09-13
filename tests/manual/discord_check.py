import os, json, urllib.request, urllib.error
url = os.environ.get("DISCORD_WEBHOOK_URL")
if not url:
    print("No DISCORD_WEBHOOK_URL set"); raise SystemExit(2)
payload = {"content": "✅ sb-watchbot: discord_check OK"}
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
try:
    with urllib.request.urlopen(req, timeout=8) as resp:
        print("Discord HTTP:", resp.status)
        print("OK (HTTP 204 is typical)")
except urllib.error.HTTPError as e:
    print("Discord HTTPError:", e.code, e.read().decode("utf-8", "ignore"))
    raise
