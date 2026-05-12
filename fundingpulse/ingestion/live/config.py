"""Configuration objects for live funding ingestion core behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class LiveEnqueuerConfig:
    """Runtime-independent knobs for one live enqueue tick."""

    enqueue_timeout: timedelta = timedelta(seconds=45)
    task_timeout: timedelta = timedelta(seconds=45)
    stale_running_grace: timedelta = timedelta(seconds=15)
