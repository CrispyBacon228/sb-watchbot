import csv
from pathlib import Path

from sbwatch.preflight import analyze_bars

# Try to import notify; if that fails, fall back to print-only mode
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
                o = row.get("open") or row.get("o")
                h = row.get("high") or row.get("h")
                l = row.get("low") or row.get("l")
                c = row.get("close") or row.get("c")
                ts = row.get("ts_ms") or row.get("timestamp") or row.get("ts")
                rows.append(
                    {
                        "ts_ms": int(float(ts)),
                        "o": float(o),
                        "h": float(h),
                        "l": float(l),
                        "c": float(c),
                    }
                )
            except Exception:
                continue

    return rows[-n:] if len(rows) > n else rows


def send(msg: str):
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

    # direction note: are longs/shorts in bias?
    if result.status == "CHOP":
        dir_note = "Both LONGS and SHORTS are high-risk (choppy / low-quality tape)."
    else:
        if result.bias == "BULL":
            if result.long_ok and not result.short_ok:
                dir_note = "LONGS are in bias; SHORTS are countertrend."
            elif result.long_ok and result.short_ok:
                dir_note = "Bias slightly bullish; both directions tradable but LONGS favored."
            else:
                dir_note = "Bullish tilt but structure is weak — treat LONGS as high risk."
        elif result.bias == "BEAR":
            if result.short_ok and not result.long_ok:
                dir_note = "SHORTS are in bias; LONGS are countertrend (avoid SB longs)."
            elif result.short_ok and result.long_ok:
                dir_note = "Bias slightly bearish; both directions tradable but SHORTS favored."
            else:
                dir_note = "Bearish tilt but structure is weak — treat SHORTS as high risk."
        else:
            dir_note = "No clear directional bias — both LONGS and SHORTS are marginal."

    reasons_short = "; ".join(result.reasons[:2]) if result.reasons else "No details."

    msg = (
        f"{status_emoji} SB-PREFLIGHT (09:59 ET) ➜ {result.status} | {bias_text} "
        f"| cleanliness ~{result.score:.2f}\n"
        f"• {dir_note}\n"
        f"• {reasons_short}"
    )

    send(msg)


if __name__ == "__main__":
    main()
