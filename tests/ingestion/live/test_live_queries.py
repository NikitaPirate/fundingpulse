from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.ingestion.live.constants import (
    STALE_RUNNING_ERROR_TYPE,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
)
from fundingpulse.ingestion.live.dto import LiveEnqueueTick
from fundingpulse.ingestion.live.enqueuer import build_live_funding_task_key
from fundingpulse.ingestion.live.queries import (
    get_active_live_task_exchanges,
    insert_pending_live_task,
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
