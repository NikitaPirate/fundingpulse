"""Live funding worker execution use-case."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from time import monotonic
from typing import Final

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.config import LiveWorkerConfig
from fundingpulse.ingestion.live.constants import (
    LIVE_FUNDING_PIPELINE,
    TASK_STATUS_DONE,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_TIMEOUT_ERROR_TYPE,
)
from fundingpulse.ingestion.live.dto import (
    ClaimedLiveTask,
    LiveTaskExecutionResult,
    LiveTaskHandler,
)
from fundingpulse.ingestion.live.queries import (
    get_next_pending_live_task,
    mark_live_task_done,
    mark_live_task_failed,
)
from fundingpulse.models.ingestion_task import IngestionTask
from fundingpulse.time import to_iso8601, utc_now

DEFAULT_LIVE_WORKER_CONFIG: Final = LiveWorkerConfig()

logger = logging.getLogger(__name__)


async def execute_one_live_task(
    *,
    session_factory: SessionFactory,
    worker_id: str,
    handler: LiveTaskHandler,
    config: LiveWorkerConfig = DEFAULT_LIVE_WORKER_CONFIG,
    event_logger: logging.Logger | None = None,
) -> LiveTaskExecutionResult:
    """Claim and execute one pending live funding task, if one exists."""
    log = event_logger or logger
    task = await _claim_next_pending_live_task(
        session_factory=session_factory,
        worker_id=worker_id,
    )

    if task is None:
        return LiveTaskExecutionResult(claimed=False)

    _log_task_claimed(log, task)
    started_at = monotonic()
    timeout = asyncio.timeout(config.task_timeout.total_seconds())
    try:
        async with timeout:
            await handler(task)
    except Exception as exc:
        # Catch all handler failures because the task finalization path is identical.
        error_type = TASK_TIMEOUT_ERROR_TYPE if timeout.expired() else type(exc).__name__
        error_message = _format_timeout_message(config) if timeout.expired() else str(exc)
        return await _fail_task(
            session_factory=session_factory,
            task=task,
            error_type=error_type,
            error_message=error_message,
            log=log,
            started_at=started_at,
        )

    finished_at = utc_now()
    async with session_factory.begin() as session:
        updated = await mark_live_task_done(
            session=session,
            task_key=task.task_key,
            worker_id=worker_id,
            finished_at=finished_at,
        )
    if not updated:
        raise RuntimeError(f"Running live task was not finalized: {task.task_key}")

    _log_task_event(
        log,
        "live_task_completed",
        task=task,
        duration_seconds=monotonic() - started_at,
    )
    return LiveTaskExecutionResult(
        claimed=True,
        task_key=task.task_key,
        status=TASK_STATUS_DONE,
    )


async def _claim_next_pending_live_task(
    *,
    session_factory: SessionFactory,
    worker_id: str,
) -> ClaimedLiveTask | None:
    """Claim the oldest pending live task in a short transaction."""
    async with session_factory.begin() as session:
        task = await get_next_pending_live_task(session)
        if task is None:
            return None

        task.status = TASK_STATUS_RUNNING
        task.claimed_at = utc_now()
        task.worker_id = worker_id
        task.finished_at = None
        task.error_type = None
        task.error_message = None
        await session.flush()
        return _to_claimed_live_task(task, worker_id=worker_id)


async def _fail_task(
    *,
    session_factory: SessionFactory,
    task: ClaimedLiveTask,
    error_type: str,
    error_message: str,
    log: logging.Logger,
    started_at: float,
) -> LiveTaskExecutionResult:
    finished_at = utc_now()
    async with session_factory.begin() as session:
        updated = await mark_live_task_failed(
            session=session,
            task_key=task.task_key,
            worker_id=task.worker_id,
            finished_at=finished_at,
            error_type=error_type,
            error_message=error_message,
        )
    if not updated:
        raise RuntimeError(f"Running live task was not finalized: {task.task_key}")

    _log_task_event(
        log,
        "live_task_failed",
        task=task,
        duration_seconds=monotonic() - started_at,
        error_type=error_type,
        error_message=error_message,
    )
    return LiveTaskExecutionResult(
        claimed=True,
        task_key=task.task_key,
        status=TASK_STATUS_FAILED,
        error_type=error_type,
        error_message=error_message,
    )


def _to_claimed_live_task(
    task: IngestionTask,
    *,
    worker_id: str,
) -> ClaimedLiveTask:
    if task.claimed_at is None:
        raise ValueError(f"Claimed task is missing claimed_at: {task.task_key}")

    return ClaimedLiveTask(
        task_key=task.task_key,
        exchange=task.exchange_name,
        scheduled_for=task.scheduled_for,
        payload=dict(task.payload),
        created_at=task.created_at,
        claimed_at=task.claimed_at,
        worker_id=worker_id,
    )


def _log_task_claimed(log: logging.Logger, task: ClaimedLiveTask) -> None:
    queue_wait_seconds = (task.claimed_at - task.created_at).total_seconds()
    _log_task_event(
        log,
        "live_task_claimed",
        task=task,
        queue_wait_seconds=queue_wait_seconds,
    )


def _log_task_event(
    log: logging.Logger,
    event: str,
    *,
    task: ClaimedLiveTask,
    **fields: object,
) -> None:
    _log_event(
        log,
        event,
        pipeline=LIVE_FUNDING_PIPELINE,
        task_key=task.task_key,
        exchange=task.exchange,
        scheduled_for=to_iso8601(task.scheduled_for),
        worker_id=task.worker_id,
        **fields,
    )


def _log_event(log: logging.Logger, event: str, **fields: object) -> None:
    extra: Mapping[str, object] = {"event": event, **fields}
    log.info(event, extra=extra)


def _format_timeout_message(config: LiveWorkerConfig) -> str:
    timeout_seconds = config.task_timeout.total_seconds()
    return f"Task timed out after {timeout_seconds:g}s"
