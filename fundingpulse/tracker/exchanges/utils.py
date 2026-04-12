"""Common utilities for exchange adapters."""

from datetime import datetime


def to_ms_timestamp(dt: datetime | None) -> int:
    """Convert datetime to milliseconds since Unix epoch; None returns 0."""
    return int(dt.timestamp() * 1000) if dt else 0


def to_sec_timestamp(dt: datetime | None) -> int:
    """Convert datetime to seconds since Unix epoch; None returns 0."""
    return int(dt.timestamp()) if dt else 0


def from_ms_timestamp(ms: int) -> datetime:
    """Parse milliseconds timestamp to datetime."""
    return datetime.fromtimestamp(ms / 1000.0)


def from_sec_timestamp(sec: int) -> datetime:
    """Parse seconds timestamp to datetime."""
    return datetime.fromtimestamp(sec)
