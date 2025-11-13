import os
os.environ["WINDOW_START"] = "00:00"
os.environ["WINDOW_END"] = "23:59"

from sbwatch.strategy import SBEngine

def ts(minute, second):
    return minute * 60_000 + second * 1000

def feed_tick(eng, minute, second, o,h,l,c):
    eng.on_bar(ts(minute, second), o,h,l,c)

def feed_minute_close(eng, minute, o,h,l,c):
    # last tick of the minute at second=59
    eng.on_bar(ts(minute, 59), o,h,l,c)

def run():
    levels = {"pdh": -1e9, "pdl": 1e9, "asia_high": -1e9, "asia_low": 1e9,
              "london_high": -1e9, "london_low": 1e9}

    eng = SBEngine(levels)
    entries = []

    def fake_notify(**kw):
        entries.append(kw)
        print("ENTRY:", kw)

    eng._notify = fake_notify
    eng._resolve_notify_callable()

    # seed three completed minutes
    feed_minute_close(eng, 0, 100,101, 99,100)
    feed_minute_close(eng, 1, 100,101, 99,100)
    feed_minute_close(eng, 2, 100,105, 95,100)

    # minute 3 close builds the FVG
    # A3-B2-C1 mapping results in a bull FVG at gap_top = 100
    feed_minute_close(eng, 3, 100,105,95,100)

    # Now minute 4 starts — this is where intraminute returns are tested
    # At 4:00:01, price returns into the FVG level 100
    feed_tick(eng, 4, 1, 100,100,100,100)

    print("\nTOTAL ENTRIES:", len(entries))
    for e in entries:
        print(e)

if __name__ == "__main__":
    run()
