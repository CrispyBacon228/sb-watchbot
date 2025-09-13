import json, os, time, urllib.parse, urllib.request, urllib.error

WEBHOOK = os.getenv("DISCORD_WEBHOOK","").strip()

def _post_json(url, payload, timeout=5):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type":"application/json; charset=utf-8",
                 "User-Agent":"sb-watchbot/alerts"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()
    return True

def _post_form(url, text, timeout=5):
    # Slack-compatible: payload is form field "payload" with a JSON string
    form = urllib.parse.urlencode({"payload": json.dumps({"text": text})}).encode()
    req  = urllib.request.Request(
        url,
        data=form,
        headers={"Content-Type":"application/x-www-form-urlencoded; charset=utf-8",
                 "User-Agent":"sb-watchbot/alerts"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()
    return True

def dispatch(evt):
    if not WEBHOOK:
        print("⚠ No DISCORD_WEBHOOK set")
        return False

    text = (evt.get("content") or evt.get("note") or evt.get("text")
            or json.dumps(evt, ensure_ascii=False))
    url  = WEBHOOK

    # Prefer getting a 200 during debugging
    if "wait=" not in url:
        url = url + ("&wait=true" if "?" in url else "?wait=true")

    is_slack = url.rstrip("/").endswith("/slack")
    for i in range(3):
        try:
            if is_slack:
                return _post_form(url, text)
            else:
                return _post_json(url, {"content": str(text)})
        except Exception as e:
            print(f"Discord send failed: {e}")
            time.sleep(1 + i)
    return False
