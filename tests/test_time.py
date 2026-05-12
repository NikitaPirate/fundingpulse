from __future__ import annotations

from fundingpulse.time import from_iso8601, start_of_minute, utc_datetime


def test_start_of_minute_uses_utc_minute() -> None:
    value = from_iso8601("2026-05-08T14:34:56.789000+02:00")

    assert start_of_minute(value) == utc_datetime(2026, 5, 8, 12, 34)
