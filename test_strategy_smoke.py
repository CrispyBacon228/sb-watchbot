import os

# Make the entry window the full day so the time filter never blocks our test.
os.environ["WINDOW_START"] = "00:00"
os.environ["WINDOW_END"] = "23:59"

from sbwatch.strategy import SBEngine

def make_ts(minute: int) -> int:
    # Just need strictly increasing minute-buckets; actual date doesn't matter.
    return minute * 60_000  # ms since epoch

def feed_bar(engine: SBEngine, minute: int, o: float, h: float, l: float, c: float):
    ts = make_ts(minute)
    engine.on_bar(ts, o, h, l, c)

def run_tests():
    # Levels chosen so sweeps are always "true" (just for testing logic).
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
        print("ENTRY:", kw)

    # wire fake notify into the engine
    eng._notify = fake_notify
    eng._resolve_notify_callable()

    # ---- seed a few minutes to stabilize A/B/C ----
    feed_bar(eng, 0, 100.0, 101.0,  99.0, 100.0)
    feed_bar(eng, 1, 100.0, 101.0,  99.0, 100.0)
    feed_bar(eng, 2, 100.0, 101.0,  99.0, 100.0)
    # minute 3 candle (this will be C0 when we roll into minute 4)
    feed_bar(eng, 3, 100.0, 105.0,  95.0, 100.0)

    print("After seeding, synthetic bar index i =", eng._i)

    # ---- force a bull FVG 'return' ----
    # On the NEXT minute rollover (into minute 4), C0 will be the minute-3 bar,
    # which has low=95, high=105. So we pick gap_top=100 so it's INSIDE that bar.
    eng._last_bull = {
        "i": eng._i,
        "gap_top": 100.0,  # should satisfy C0['l'] <= gap_top <= C0['h']
        "gap_bot": 98.0,
        "disp": 0.5,
        "c1_low": 95.0,
        "c1_high": 101.0,
    }

    # trigger new minute -> should fire a LONG if the return logic is correct
    feed_bar(eng, 4, 101.0, 102.0, 100.0, 101.5)

    # ---- force a bear FVG 'return' ----
    # On the next rollover (into minute 5), C0 will be the minute-4 bar,
    # which has low=100, high=102. So pick gap_bot=101 inside that range.
    eng._last_bear = {
        "i": eng._i,
        "gap_top": 103.0,
        "gap_bot": 101.0,  # C0['l'] <= gap_bot <= C0['h']
        "disp": 0.5,
        "c1_low": 101.0,
        "c1_high": 103.0,
    }

    feed_bar(eng, 5, 101.0, 103.0, 100.0, 101.5)

    print("\nTotal entries generated in test:", len(entries))
    for idx, e in enumerate(entries, 1):
        print(f"{idx}. side={e.get('side')} entry={e.get('entry')} when={e.get('when')}")

if __name__ == "__main__":
    run_tests()
