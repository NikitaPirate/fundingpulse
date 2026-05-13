"""Database queries for live funding ingestion scheduling."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, col

from fundingpulse.ingestion.live.constants import (
    LIVE_FUNDING_PIPELINE,
    STALE_RUNNING_ERROR_MESSAGE,
    STALE_RUNNING_ERROR_TYPE,
    TASK_STATUS_DONE,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
)
from fundingpulse.ingestion.live.dto import LiveEnqueueTick
from fundingpulse.models.ingestion_task import IngestionTask
from fundingpulse.time import UtcDateTime


class SQLModelWithTable(SQLModel):
    """SQLModel class with a SQLAlchemy table object."""

    __table__: Any


async def mark_stale_running_live_tasks_failed(
    *,
    session: AsyncSession,
    tick: LiveEnqueueTick,
) -> list[str]:
    """Mark stale running live tasks failed and return their task keys."""
    stmt = (
        update(IngestionTask)
        .where(
            col(IngestionTask.pipeline) == LIVE_FUNDING_PIPELINE,
            col(IngestionTask.status) == TASK_STATUS_RUNNING,
            col(IngestionTask.claimed_at).is_not(None),
            col(IngestionTask.claimed_at) < tick.stale_before,
        )
        .values(
            status=TASK_STATUS_FAILED,
            finished_at=tick.now,
            error_type=STALE_RUNNING_ERROR_TYPE,
            error_message=STALE_RUNNING_ERROR_MESSAGE,
        )
        .returning(col(IngestionTask.task_key))
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def get_active_live_task_exchanges(
    session: AsyncSession,
    exchanges: Collection[str],
) -> set[str]:
    """Return exchanges with active pending or running live work."""
    if not exchanges:
        return set()

    stmt = (
        select(col(IngestionTask.exchange_name))
        .where(
            col(IngestionTask.pipeline) == LIVE_FUNDING_PIPELINE,
            col(IngestionTask.exchange_name).in_(exchanges),
            col(IngestionTask.status).in_([TASK_STATUS_PENDING, TASK_STATUS_RUNNING]),
        )
        .distinct()
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def insert_pending_live_task(
    *,
    session: AsyncSession,
    task_key: str,
    exchange: str,
    scheduled_for: UtcDateTime,
) -> bool:
    """Insert a pending live task, returning whether a row was created."""
    task_table = cast(type[SQLModelWithTable], IngestionTask).__table__
    stmt = (
        pg_insert(task_table)
        .values(
            task_key=task_key,
            pipeline=LIVE_FUNDING_PIPELINE,
            exchange_name=exchange,
            scheduled_for=scheduled_for,
            payload={},
            status=TASK_STATUS_PENDING,
        )
        .on_conflict_do_nothing(index_elements=["task_key"])
        .returning(task_table.c.task_key)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_next_pending_live_task(session: AsyncSession) -> IngestionTask | None:
    """Return the oldest pending live task locked for update."""
    stmt = (
        select(IngestionTask)
        .where(
            col(IngestionTask.pipeline) == LIVE_FUNDING_PIPELINE,
            col(IngestionTask.status) == TASK_STATUS_PENDING,
        )
        .order_by(col(IngestionTask.created_at), col(IngestionTask.task_key))
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_live_task_done(
    *,
    session: AsyncSession,
    task_key: str,
    worker_id: str,
    finished_at: UtcDateTime,
) -> bool:
    """Mark a worker-owned running live task done."""
    stmt = (
        update(IngestionTask)
        .where(
            col(IngestionTask.task_key) == task_key,
            col(IngestionTask.pipeline) == LIVE_FUNDING_PIPELINE,
            col(IngestionTask.status) == TASK_STATUS_RUNNING,
            col(IngestionTask.worker_id) == worker_id,
        )
        .values(
            status=TASK_STATUS_DONE,
            finished_at=finished_at,
            error_type=None,
            error_message=None,
        )
        .returning(col(IngestionTask.task_key))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_live_task_failed(
    *,
    session: AsyncSession,
    task_key: str,
    worker_id: str,
    finished_at: UtcDateTime,
    error_type: str,
    error_message: str,
) -> bool:
    """Mark a worker-owned running live task failed."""
    stmt = (
        update(IngestionTask)
        .where(
            col(IngestionTask.task_key) == task_key,
            col(IngestionTask.pipeline) == LIVE_FUNDING_PIPELINE,
            col(IngestionTask.status) == TASK_STATUS_RUNNING,
            col(IngestionTask.worker_id) == worker_id,
        )
        .values(
            status=TASK_STATUS_FAILED,
            finished_at=finished_at,
            error_type=error_type,
            error_message=error_message,
        )
        .returning(col(IngestionTask.task_key))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
