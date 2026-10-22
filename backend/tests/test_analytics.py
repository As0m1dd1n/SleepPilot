from datetime import datetime, timezone

from app.analytics import duration_hours
from app.models import SleepEntry


def test_duration_hours():
    entry = SleepEntry(
        bedtime=datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc),
        wake_time=datetime(2026, 1, 2, 7, 30, tzinfo=timezone.utc),
    )
    assert duration_hours(entry) == 8.5
