from datetime import datetime, time, timezone
def in_ny_killzone(dt: datetime) -> bool:
    t = dt.astimezone(timezone.utc).time()
    # placeholder; adjust to ET in real code
    return time(14,0) <= t <= time(15,0)
