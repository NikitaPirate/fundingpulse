from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.ingestion.live.constants import (
    LIVE_FUNDING_PIPELINE,
    STALE_RUNNING_ERROR_TYPE,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
)
from fundingpulse.ingestion.live.enqueuer import (
    build_live_funding_task_key,
    enqueue_live_funding_tick,
)
from fundingpulse.time import utc_datetime
from tests.ingestion.live.helpers import (
    RecordingEventLogger,
    all_ingestion_tasks,
    insert_ingestion_task,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


async def test_enqueue_live_funding_tick_creates_one_task_per_selected_exchange(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    event_logger = RecordingEventLogger()
    now = utc_datetime(2026, 5, 8, 12, 34, 56)

    result = await enqueue_live_funding_tick(
        session_factory=ingestion_session_factory,
        exchanges=["bybit", "okx"],
        now=now,
        event_logger=event_logger,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert [(task.exchange_name, task.status) for task in tasks] == [
        ("bybit", TASK_STATUS_PENDING),
        ("okx", TASK_STATUS_PENDING),
    ]
    assert all(task.pipeline == LIVE_FUNDING_PIPELINE for task in tasks)
    assert all(task.scheduled_for == utc_datetime(2026, 5, 8, 12, 34) for task in tasks)
    assert result.created_tasks == 2
    assert result.skipped_active_tasks == 0
    assert result.stale_failed_tasks == 0

    events = [record.event for record in event_logger.records]
    assert "live_enqueue_started" in events
    assert events.count("live_task_created") == 2
    assert "live_enqueue_completed" in events

    created_record = next(
        record
        for record in event_logger.records
        if record.event == "live_task_created" and record.exchange == "bybit"
    )
    created_fields = created_record.__dict__
    assert created_fields["pipeline"] == LIVE_FUNDING_PIPELINE
    assert created_fields["scheduled_for"] == "2026-05-08T12:34:00Z"
    assert created_fields["task_key"] == build_live_funding_task_key(
        "bybit",
        utc_datetime(2026, 5, 8, 12, 34),
    )


async def test_enqueue_live_funding_tick_skips_exchange_with_existing_pending_work(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    event_logger = RecordingEventLogger()
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 33),
    )

    result = await enqueue_live_funding_tick(
        session_factory=ingestion_session_factory,
        exchanges=["bybit", "okx"],
        now=utc_datetime(2026, 5, 8, 12, 34, 56),
        event_logger=event_logger,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert [(task.exchange_name, task.scheduled_for, task.status) for task in tasks] == [
        ("bybit", utc_datetime(2026, 5, 8, 12, 33), TASK_STATUS_PENDING),
        ("okx", utc_datetime(2026, 5, 8, 12, 34), TASK_STATUS_PENDING),
    ]
    assert result.created_tasks == 1
    assert result.skipped_active_tasks == 1

    skipped_record = next(
        record
        for record in event_logger.records
        if record.event == "live_task_skipped" and record.exchange == "bybit"
    )
    skipped_fields = skipped_record.__dict__
    assert skipped_fields["reason"] == "active_work"
    assert skipped_fields["scheduled_for"] == "2026-05-08T12:34:00Z"


async def test_enqueue_live_funding_tick_fails_stale_running_work_before_scheduling_current_task(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 34, 56)
    stale_scheduled_for = utc_datetime(2026, 5, 8, 12, 32)
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_RUNNING,
        scheduled_for=stale_scheduled_for,
        claimed_at=now - timedelta(minutes=2),
    )

    result = await enqueue_live_funding_tick(
        session_factory=ingestion_session_factory,
        exchanges=["bybit"],
        now=now,
        config=LiveEnqueuerConfig(task_timeout=timedelta(seconds=45)),
    )

    tasks = await all_ingestion_tasks(db_session)
    assert [(task.scheduled_for, task.status) for task in tasks] == [
        (stale_scheduled_for, TASK_STATUS_FAILED),
        (utc_datetime(2026, 5, 8, 12, 34), TASK_STATUS_PENDING),
    ]
    stale_task = tasks[0]
    assert stale_task.finished_at == now
    assert stale_task.error_type == STALE_RUNNING_ERROR_TYPE
    assert result.stale_failed_tasks == 1
    assert result.created_tasks == 1
    assert result.skipped_active_tasks == 0
