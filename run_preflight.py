import os
import csv
from pathlib import Path

from sbwatch.preflight import analyze_bars

# Try to import notify; if that fails, we fall back to print-only mode
try:
    from sbwatch import notify
except Exception:
    notify = None

DATA_PATH = Path("data/live_minute.csv")

def load_last_bars(n: int = 30):
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} not found")

    rows = []
    with DATA_PATH.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Support both styles: open/high/low/close OR o/h/l/c
                o = row.get("open") or row.get("o")
                h = row.get("high") or row.get("h")
                l = row.get("low") or row.get("l")
                c = row.get("close") or row.get("c")
                ts = row.get("ts_ms") or row.get("timestamp") or row.get("ts")

                rows.append({
                    "ts_ms": int(float(ts)),
                    "o": float(o),
                    "h": float(h),
                    "l": float(l),
                    "c": float(c),
                })
            except Exception:
                # skip bad lines
                continue

    return rows[-n:] if len(rows) > n else rows

def send(msg: str):
    """Send to Discord if possible, and always print to stdout."""
    print(msg)
    if notify is not None:
        try:
            notify.post_discord(msg)
        except Exception as e:
            print(f"[preflight notify error: {e}]")

def main():
    try:
        bars = load_last_bars(30)
    except Exception as e:
        send(f"🧪 SB-PREFLIGHT (09:59 ET) ➜ ERROR loading minute data: {e}")
        return

    result = analyze_bars(bars)

    status_emoji = {
        "CLEAN": "✅",
        "MIXED": "⚠️",
        "CHOP": "❌",
        "UNKNOWN": "❓",
    }.get(result.status, "❓")

    bias_text = {
        "BULL": "Bullish tilt",
        "BEAR": "Bearish tilt",
        "NEUTRAL": "No clear bias",
    }.get(result.bias, "No clear bias")

    reasons_short = "; ".join(result.reasons[:2]) if result.reasons else "No details."

    msg = (
        f"{status_emoji} SB-PREFLIGHT (09:59 ET) ➜ {result.status} | {bias_text} "
        f"| cleanliness score ~{result.score:.2f}\n"
        f"• {reasons_short}"
    )

    send(msg)

if __name__ == "__main__":
    main()
