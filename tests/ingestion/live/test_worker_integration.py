from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.config import LiveWorkerConfig
from fundingpulse.ingestion.live.constants import (
    LIVE_FUNDING_PIPELINE,
    TASK_STATUS_DONE,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_TIMEOUT_ERROR_TYPE,
)
from fundingpulse.ingestion.live.dto import ClaimedLiveTask
from fundingpulse.ingestion.live.worker import execute_one_live_task
from fundingpulse.time import utc_datetime
from tests.ingestion.live.helpers import (
    all_ingestion_tasks,
    insert_ingestion_task,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


async def test_execute_one_live_task_returns_unclaimed_when_no_pending_task(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    called = False

    async def handler(task: ClaimedLiveTask) -> None:
        nonlocal called
        called = True
        del task

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        handler=handler,
    )

    assert result.claimed is False
    assert called is False
    assert await all_ingestion_tasks(db_session) == []


async def test_execute_one_live_task_runs_handler_and_marks_task_done(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event_logger = logging.getLogger("tests.ingestion.live_worker.success")
    caplog.set_level(logging.INFO, logger=event_logger.name)
    scheduled_for = utc_datetime(2026, 5, 8, 12, 30)
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
    )
    handled_tasks: list[ClaimedLiveTask] = []

    async def handler(task: ClaimedLiveTask) -> None:
        handled_tasks.append(task)

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        handler=handler,
        event_logger=event_logger,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_DONE
    assert len(handled_tasks) == 1
    assert handled_tasks[0].exchange == "bybit"
    assert handled_tasks[0].scheduled_for == scheduled_for
    assert tasks[0].status == TASK_STATUS_DONE
    assert tasks[0].worker_id == "worker-1"
    assert tasks[0].claimed_at is not None
    assert tasks[0].finished_at is not None

    events = [getattr(record, "event", None) for record in caplog.records]
    assert "live_task_claimed" in events
    assert "live_task_completed" in events
    completed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "live_task_completed"
    )
    completed_fields = completed_record.__dict__
    assert completed_fields["pipeline"] == LIVE_FUNDING_PIPELINE
    assert completed_fields["exchange"] == "bybit"
    assert completed_fields["worker_id"] == "worker-1"
    assert completed_fields["scheduled_for"] == "2026-05-08T12:30:00Z"


async def test_execute_one_live_task_executes_task_scheduled_in_the_past(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 1)
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="okx",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
    )
    handled_scheduled_for: list[object] = []

    async def handler(task: ClaimedLiveTask) -> None:
        handled_scheduled_for.append(task.scheduled_for)

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        handler=handler,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.status == TASK_STATUS_DONE
    assert handled_scheduled_for == [scheduled_for]
    assert tasks[0].status == TASK_STATUS_DONE


async def test_execute_one_live_task_marks_handler_exception_failed(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event_logger = logging.getLogger("tests.ingestion.live_worker.failure")
    caplog.set_level(logging.INFO, logger=event_logger.name)
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
    )

    async def handler(task: ClaimedLiveTask) -> None:
        del task
        raise RuntimeError("boom")

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        handler=handler,
        event_logger=event_logger,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_FAILED
    assert result.error_type == "RuntimeError"
    assert result.error_message == "boom"
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == "RuntimeError"
    assert tasks[0].error_message == "boom"

    failed_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "live_task_failed"
    )
    failed_fields = failed_record.__dict__
    assert failed_fields["error_type"] == "RuntimeError"
    assert failed_fields["error_message"] == "boom"


async def test_execute_one_live_task_preserves_handler_timeout_error(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
    )

    async def handler(task: ClaimedLiveTask) -> None:
        del task
        raise TimeoutError("upstream timeout")

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        handler=handler,
        config=LiveWorkerConfig(task_timeout=timedelta(seconds=45)),
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_FAILED
    assert result.error_type == "TimeoutError"
    assert result.error_message == "upstream timeout"
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == "TimeoutError"
    assert tasks[0].error_message == "upstream timeout"


async def test_execute_one_live_task_marks_timeout_failed(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
    )

    async def handler(task: ClaimedLiveTask) -> None:
        del task
        await asyncio.sleep(1)

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        handler=handler,
        config=LiveWorkerConfig(task_timeout=timedelta(milliseconds=10)),
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_FAILED
    assert result.error_type == TASK_TIMEOUT_ERROR_TYPE
    assert result.error_message == "Task timed out after 0.01s"
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == TASK_TIMEOUT_ERROR_TYPE
    assert tasks[0].error_message == "Task timed out after 0.01s"
