import os
os.environ["WINDOW_START"] = "00:00"
os.environ["WINDOW_END"] = "23:59"

from sbwatch.strategy import SBEngine

def ts(minute, second):
    return minute * 60_000 + second * 1000

def feed_tick(eng, minute, second, o,h,l,c):
    print(f"[TICK] {minute}:{second:02d}  o={o} h={h} l={l} c={c}")
    eng.on_bar(ts(minute, second), o,h,l,c)

def feed_minute_close(eng, minute, o,h,l,c):
    # simulate the last tick of that minute at :59
    print(f"[MINUTE CLOSE] {minute}:59  o={o} h={h} l={l} c={c}")
    eng.on_bar(ts(minute, 59), o,h,l,c)

def run():
    # levels chosen so sweeps are always true: any normal high > -1e9, any low < 1e9
    levels = {
        "pdh": -1e9,
        "pdl":  1e9,
        "asia_high": -1e9,
        "asia_low":  1e9,
        "london_high": -1e9,
        "london_low":  1e9,
    }

    eng = SBEngine(levels)
    entries = []

    def fake_notify(**kw):
        entries.append(kw)
        print(">>> ENTRY FIRED:", kw)

    eng._notify = fake_notify
    eng._resolve_notify_callable()

    print("\n--- Seeding minutes (0,1,2) to form a bull FVG ---")
    # minute 0: base candle (A0.high = 100)
    feed_minute_close(eng, 0, 100, 100, 95, 96)

    # minute 1: big bullish displacement candle (B0)
    # range = 105 - 98 = 7, body = 104 - 99 = 5, disp ~ 0.71 (> 0.3)
    feed_minute_close(eng, 1, 99, 105, 98, 104)

    # minute 2: strong up candle with low ABOVE minute-0 high
    # C0.low = 102, A0.high = 100 => 2pt FVG (bull)
    feed_minute_close(eng, 2, 103, 110, 102, 109)

    print("\n--- Minute 3 close (this is where FVG from 0,1,2 is evaluated) ---")
    # minute 3 itself can be anything; it's just the trigger for evaluating 0,1,2
    feed_minute_close(eng, 3, 105, 108, 101, 106)

    print("\n[DEBUG] _last_bull =", eng._last_bull)
    print("[DEBUG] _last_bear =", eng._last_bear)

    # At this point we expect a bull FVG stored in _last_bull:
    #   gap_top ~ 102, gap_bot ~ 100

    print("\n--- Intraminute test: minute 3, second 1 (intraminute return) ---")
    # Now in the SAME minute bucket (3), we send a 1s tick that trades through the gap_top.
    # Make the candle contain 102 so it "returns into" the FVG:
    #   low = 101 <= 102 <= high = 103
    feed_tick(eng, 3, 1, 102, 103, 101, 102.5)

    print("\nTOTAL ENTRIES:", len(entries))
    for e in entries:
        print(e)

if __name__ == "__main__":
    run()
