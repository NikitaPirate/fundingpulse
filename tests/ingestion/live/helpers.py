from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.constants import LIVE_FUNDING_PIPELINE
from fundingpulse.ingestion.live.enqueuer import build_live_funding_task_key
from fundingpulse.models.ingestion_task import IngestionTask
from fundingpulse.time import UtcDateTime


async def all_ingestion_tasks(session: AsyncSession) -> list[IngestionTask]:
    result = await session.execute(
        select(IngestionTask).order_by(
            col(IngestionTask.exchange_name),
            col(IngestionTask.scheduled_for),
        )
    )
    return list(result.scalars().all())


async def add_ingestion_task(
    session: AsyncSession,
    *,
    exchange: str,
    status: str,
    scheduled_for: UtcDateTime,
    claimed_at: UtcDateTime | None = None,
) -> IngestionTask:
    task = IngestionTask(
        task_key=build_live_funding_task_key(exchange, scheduled_for),
        pipeline=LIVE_FUNDING_PIPELINE,
        exchange_name=exchange,
        scheduled_for=scheduled_for,
        payload={},
        status=status,
        claimed_at=claimed_at,
    )
    session.add(task)
    await session.flush()
    return task


async def insert_ingestion_task(
    session_factory: SessionFactory,
    *,
    exchange: str,
    status: str,
    scheduled_for: UtcDateTime,
    claimed_at: UtcDateTime | None = None,
) -> None:
    async with session_factory.begin() as session:
        await add_ingestion_task(
            session,
            exchange=exchange,
            status=status,
            scheduled_for=scheduled_for,
            claimed_at=claimed_at,
        )
