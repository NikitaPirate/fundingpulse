"""Shared constants for live funding ingestion."""

from typing import Final

LIVE_FUNDING_PIPELINE: Final = "live_funding"
LIVE_FUNDING_TASK_KEY_PREFIX: Final = "live_funding_snapshot"
TASK_STATUS_PENDING: Final = "pending"
TASK_STATUS_RUNNING: Final = "running"
TASK_STATUS_FAILED: Final = "failed"
STALE_RUNNING_ERROR_TYPE: Final = "stale_running_task"
STALE_RUNNING_ERROR_MESSAGE: Final = "Task was still running past the live worker timeout"
