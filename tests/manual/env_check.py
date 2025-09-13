import os, sys, json, pathlib
root = pathlib.Path(__file__).resolve().parents[2]
print("Repo root:", root)
print("Python:", sys.executable)
keys = ["DATABENTO_API_KEY","DB_DATASET","DB_SCHEMA","FRONT_SYMBOL",
        "PRICE_DIVISOR","DISCORD_WEBHOOK_URL","REPLAY_ET_DATE"]
print("ENV snapshot:")
print(json.dumps({k: os.environ.get(k) for k in keys}, indent=2))
