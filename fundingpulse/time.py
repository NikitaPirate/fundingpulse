"""Canonical UTC time API for the whole project."""

from __future__ import annotations

from datetime import UTC, datetime

UtcDateTime = datetime  # noqa: UP040


def utc_now() -> UtcDateTime:
    """Return the current UTC instant as an aware datetime."""
    return datetime.now(UTC)


def utc_datetime(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> UtcDateTime:
    """Build a fixed UTC datetime."""
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        microsecond,
        tzinfo=UTC,
    )


def from_unix_seconds(value: int | float) -> UtcDateTime:
    """Convert Unix seconds to an aware UTC datetime."""
    return datetime.fromtimestamp(value, UTC)


def from_unix_milliseconds(value: int | float) -> UtcDateTime:
    """Convert Unix milliseconds to an aware UTC datetime."""
    return from_unix_seconds(value / 1000.0)


def from_iso8601(value: str) -> UtcDateTime:
    """Parse an ISO8601 timestamp with an explicit timezone and convert to UTC."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timezone-aware ISO8601 timestamp required: {value!r}")
    return parsed.astimezone(UTC)


def from_utc_iso8601(value: str) -> UtcDateTime:
    """Parse an ISO8601 timestamp that is defined by an upstream API as UTC."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def to_unix_seconds(value: UtcDateTime) -> int:
    """Convert an aware UTC datetime to Unix seconds."""
    return int(_require_aware_utc(value).timestamp())


def to_unix_milliseconds(value: UtcDateTime) -> int:
    """Convert an aware UTC datetime to Unix milliseconds."""
    return int(_require_aware_utc(value).timestamp() * 1000)


def to_iso8601(value: UtcDateTime) -> str:
    """Format an aware UTC datetime as an ISO8601 string with trailing Z."""
    return _require_aware_utc(value).isoformat().replace("+00:00", "Z")


def start_of_hour(value: UtcDateTime) -> UtcDateTime:
    """Round an aware UTC datetime down to the start of the hour."""
    return _require_aware_utc(value).replace(minute=0, second=0, microsecond=0)


def _require_aware_utc(value: UtcDateTime) -> UtcDateTime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"Expected aware UTC datetime, got naive value: {value!r}")
    return value.astimezone(UTC)
