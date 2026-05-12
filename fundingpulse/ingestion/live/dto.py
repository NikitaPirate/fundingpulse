"""DTOs and value objects for live funding ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.time import UtcDateTime, from_unix_seconds, start_of_minute


@dataclass(frozen=True, slots=True)
class LiveEnqueueTick:
    """Computed scheduling context for one live enqueue tick."""

    now: UtcDateTime
    scheduled_for: UtcDateTime
    stale_before: UtcDateTime

    @classmethod
    def from_instant(cls, now: UtcDateTime, config: LiveEnqueuerConfig) -> LiveEnqueueTick:
        scheduled_for = start_of_minute(now)
        utc_instant = from_unix_seconds(now.timestamp())
        stale_before = utc_instant - config.task_timeout - config.stale_running_grace
        return cls(now=utc_instant, scheduled_for=scheduled_for, stale_before=stale_before)


@dataclass(frozen=True, slots=True)
class LiveEnqueueResult:
    """Observable outcome of one live funding enqueue tick."""

    scheduled_for: UtcDateTime
    selected_exchanges: int
    created_tasks: int
    skipped_active_tasks: int
    duplicate_tasks: int
    stale_failed_tasks: int
