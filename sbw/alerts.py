import os, json, urllib.request

WEBHOOK = os.getenv("DISCORD_WEBHOOK")

def dispatch(event: dict):
    if not WEBHOOK:
        print("⚠️ No DISCORD_WEBHOOK set")
        return
    data = json.dumps({"content": f"📢 {event}"}).encode()
    req = urllib.request.Request(WEBHOOK, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status != 204:
            raise RuntimeError(f"Discord error {resp.status}")
