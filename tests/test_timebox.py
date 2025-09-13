from datetime import datetime, timezone
from sbwatch.core.timebox import in_ny_killzone
def test_killzone_false():
    assert in_ny_killzone(datetime(2025,1,1,12,0,tzinfo=timezone.utc)) is False
