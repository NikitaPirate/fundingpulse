"""DTOs and value objects for live funding ingestion."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True, slots=True)
class ClaimedLiveTask:
    """Scalar carrier for a claimed live funding task."""

    task_key: str
    exchange: str
    scheduled_for: UtcDateTime
    payload: dict[str, Any]
    created_at: UtcDateTime
    claimed_at: UtcDateTime
    worker_id: str


@dataclass(frozen=True, slots=True)
class LiveTaskExecutionResult:
    """Observable outcome of one live worker execution attempt."""

    claimed: bool
    task_key: str | None = None
    status: str | None = None
    error_type: str | None = None
    error_message: str | None = None


LiveTaskHandler = Callable[[ClaimedLiveTask], Awaitable[None]]
