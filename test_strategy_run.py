import time
from importlib import reload
import sbwatch.strategy as stratmod
reload(stratmod)

# find class name (class defined as SBEngine in your file)
SBEngine = getattr(stratmod, "SBEngine", None)
if SBEngine is None:
    raise SystemExit("SBEngine class not found in sbwatch.strategy")

# instantiate (pass minimal args if __init__ requires them)
try:
    bot = SBEngine({})
except TypeError:
    bot = SBEngine()

# monkeypatch notify to print so we can see posts
try:
    bot._notify = type("N",(),{"post_entry": staticmethod(lambda **kw: print("POSTED:", kw))})()
except Exception:
    bot._notify = getattr(bot, "_notify", None)

# A simple synthetic scenario:
base = int(time.time()*1000)
# first minute — create previous bars A and B so C exists
# Call on_bar to set first bar (minute start)
try:
    bot.on_bar(ts_ms=base, o=25000, h=25010, l=24990, c=25005)
    # now simulate intraminute updates (should trigger evaluation)
    for i in range(1,6):
        ts = base + i*1000
        # small moves
        o = 25005
        c = 25005 + i*0.5
        h = max(o,c) + 0.1
        l = min(o,c) - 0.1
        bot.on_bar(ts_ms=ts, o=o, h=h, l=l, c=c)
        print("called on_bar", ts, c)
except Exception as e:
    print("ERROR calling on_bar:", e)
