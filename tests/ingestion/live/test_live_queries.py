from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.ingestion.live.constants import (
    STALE_RUNNING_ERROR_TYPE,
    TASK_STATUS_DONE,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
)
from fundingpulse.ingestion.live.dto import LiveEnqueueTick
from fundingpulse.ingestion.live.enqueuer import build_live_funding_task_key
from fundingpulse.ingestion.live.queries import (
    get_active_live_task_exchanges,
    get_next_pending_live_task,
    insert_pending_live_task,
    mark_live_task_done,
    mark_live_task_failed,
    mark_stale_running_live_tasks_failed,
)
from fundingpulse.time import utc_datetime
from tests.ingestion.live.helpers import add_ingestion_task, all_ingestion_tasks

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


async def test_insert_pending_live_task_is_idempotent(db_session: AsyncSession) -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 34)
    task_key = build_live_funding_task_key("bybit", scheduled_for)

    first_created = await insert_pending_live_task(
        session=db_session,
        task_key=task_key,
        exchange="bybit",
        scheduled_for=scheduled_for,
    )
    second_created = await insert_pending_live_task(
        session=db_session,
        task_key=task_key,
        exchange="bybit",
        scheduled_for=scheduled_for,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert first_created is True
    assert second_created is False
    assert [(task.exchange_name, task.status) for task in tasks] == [
        ("bybit", TASK_STATUS_PENDING),
    ]


async def test_get_active_live_task_exchanges_returns_pending_and_running_only(
    db_session: AsyncSession,
) -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 34)
    await add_ingestion_task(
        db_session,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
    )
    await add_ingestion_task(
        db_session,
        exchange="okx",
        status=TASK_STATUS_RUNNING,
        scheduled_for=scheduled_for,
    )
    await add_ingestion_task(
        db_session,
        exchange="deribit",
        status=TASK_STATUS_FAILED,
        scheduled_for=scheduled_for,
    )

    active_exchanges = await get_active_live_task_exchanges(
        db_session,
        ["bybit", "okx", "deribit", "binance"],
    )

    assert active_exchanges == {"bybit", "okx"}


async def test_mark_stale_running_live_tasks_failed_uses_claim_threshold(
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 34, 56)
    tick = LiveEnqueueTick.from_instant(
        now,
        LiveEnqueuerConfig(task_timeout=timedelta(seconds=45)),
    )
    stale_scheduled_for = utc_datetime(2026, 5, 8, 12, 32)
    recent_scheduled_for = utc_datetime(2026, 5, 8, 12, 33)
    await add_ingestion_task(
        db_session,
        exchange="bybit",
        status=TASK_STATUS_RUNNING,
        scheduled_for=stale_scheduled_for,
        claimed_at=now - timedelta(minutes=2),
    )
    await add_ingestion_task(
        db_session,
        exchange="okx",
        status=TASK_STATUS_RUNNING,
        scheduled_for=recent_scheduled_for,
        claimed_at=now - timedelta(seconds=30),
    )

    failed_task_keys = await mark_stale_running_live_tasks_failed(
        session=db_session,
        tick=tick,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert failed_task_keys == [build_live_funding_task_key("bybit", stale_scheduled_for)]
    assert [(task.exchange_name, task.status) for task in tasks] == [
        ("bybit", TASK_STATUS_FAILED),
        ("okx", TASK_STATUS_RUNNING),
    ]
    stale_task = tasks[0]
    assert stale_task.finished_at == now
    assert stale_task.error_type == STALE_RUNNING_ERROR_TYPE


async def test_get_next_pending_live_task_returns_oldest_live_task(
    db_session: AsyncSession,
) -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 34)
    await add_ingestion_task(
        db_session,
        exchange="okx",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
        created_at=utc_datetime(2026, 5, 8, 12, 34, 2),
    )
    await add_ingestion_task(
        db_session,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
        created_at=utc_datetime(2026, 5, 8, 12, 34, 1),
    )

    task = await get_next_pending_live_task(db_session)

    tasks = await all_ingestion_tasks(db_session)
    assert task is not None
    assert task.exchange_name == "bybit"
    assert [(row.exchange_name, row.status, row.worker_id) for row in tasks] == [
        ("bybit", TASK_STATUS_PENDING, None),
        ("okx", TASK_STATUS_PENDING, None),
    ]


async def test_get_next_pending_live_task_ignores_ineligible_tasks(
    db_session: AsyncSession,
) -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 34)
    await add_ingestion_task(
        db_session,
        exchange="archive",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
        task_key="other_pipeline:archive:2026-05-08T12:34:00Z",
        pipeline="other_pipeline",
        created_at=utc_datetime(2026, 5, 8, 12, 34),
    )
    await add_ingestion_task(
        db_session,
        exchange="bybit",
        status=TASK_STATUS_RUNNING,
        scheduled_for=scheduled_for,
        created_at=utc_datetime(2026, 5, 8, 12, 34, 1),
    )
    await add_ingestion_task(
        db_session,
        exchange="okx",
        status=TASK_STATUS_FAILED,
        scheduled_for=scheduled_for,
        created_at=utc_datetime(2026, 5, 8, 12, 34, 2),
    )
    await add_ingestion_task(
        db_session,
        exchange="deribit",
        status=TASK_STATUS_DONE,
        scheduled_for=scheduled_for,
        created_at=utc_datetime(2026, 5, 8, 12, 34, 3),
    )

    task = await get_next_pending_live_task(db_session)

    assert task is None


async def test_mark_live_task_done_updates_only_worker_owned_running_task(
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 34, 56)
    scheduled_for = utc_datetime(2026, 5, 8, 12, 34)
    task = await add_ingestion_task(
        db_session,
        exchange="bybit",
        status=TASK_STATUS_RUNNING,
        scheduled_for=scheduled_for,
        claimed_at=now,
        worker_id="worker-1",
    )

    wrong_worker_updated = await mark_live_task_done(
        session=db_session,
        task_key=task.task_key,
        worker_id="worker-2",
        finished_at=now,
    )
    updated = await mark_live_task_done(
        session=db_session,
        task_key=task.task_key,
        worker_id="worker-1",
        finished_at=now,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert wrong_worker_updated is False
    assert updated is True
    assert tasks[0].status == TASK_STATUS_DONE
    assert tasks[0].finished_at == now


async def test_mark_live_task_failed_records_worker_error(
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 34, 56)
    task = await add_ingestion_task(
        db_session,
        exchange="bybit",
        status=TASK_STATUS_RUNNING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
        claimed_at=now,
        worker_id="worker-1",
    )

    wrong_worker_updated = await mark_live_task_failed(
        session=db_session,
        task_key=task.task_key,
        worker_id="worker-2",
        finished_at=now,
        error_type="RuntimeError",
        error_message="wrong worker",
    )
    updated = await mark_live_task_failed(
        session=db_session,
        task_key=task.task_key,
        worker_id="worker-1",
        finished_at=now,
        error_type="RuntimeError",
        error_message="boom",
    )

    tasks = await all_ingestion_tasks(db_session)
    assert wrong_worker_updated is False
    assert updated is True
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == "RuntimeError"
    assert tasks[0].error_message == "boom"
