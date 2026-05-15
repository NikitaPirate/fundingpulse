from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.constants import LIVE_FUNDING_PIPELINE
from fundingpulse.ingestion.live.enqueuer import build_live_funding_task_key
from fundingpulse.models.ingestion_task import IngestionTask
from fundingpulse.observability.logging import EventLogger
from fundingpulse.time import UtcDateTime


class RecordedEvent:
    def __init__(self, event: str, fields: dict[str, object]) -> None:
        self.event = event
        self.__dict__.update(fields)


class RecordingEventLogger:
    def __init__(self) -> None:
        self.records: list[RecordedEvent] = []

    def bind(self, **fields: object) -> EventLogger:
        return _BoundRecordingEventLogger(self, fields)

    def info(self, event: str, **fields: object) -> object:
        self.records.append(RecordedEvent(event, fields))
        return None

    def debug(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def warning(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def error(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def exception(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)


class _BoundRecordingEventLogger:
    def __init__(self, parent: RecordingEventLogger, bound_fields: dict[str, object]) -> None:
        self._parent = parent
        self._bound_fields = bound_fields

    @property
    def records(self) -> list[RecordedEvent]:
        return self._parent.records

    def bind(self, **fields: object) -> EventLogger:
        return _BoundRecordingEventLogger(self._parent, {**self._bound_fields, **fields})

    def info(self, event: str, **fields: object) -> object:
        self._parent.records.append(RecordedEvent(event, {**self._bound_fields, **fields}))
        return None

    def debug(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def warning(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def error(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def exception(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)


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
    task_key: str | None = None,
    pipeline: str = LIVE_FUNDING_PIPELINE,
    created_at: UtcDateTime | None = None,
    claimed_at: UtcDateTime | None = None,
    worker_id: str | None = None,
) -> IngestionTask:
    values = {
        "task_key": task_key or build_live_funding_task_key(exchange, scheduled_for),
        "pipeline": pipeline,
        "exchange_name": exchange,
        "scheduled_for": scheduled_for,
        "payload": {},
        "status": status,
        "claimed_at": claimed_at,
        "worker_id": worker_id,
    }
    if created_at is not None:
        values["created_at"] = created_at
    task = IngestionTask(**values)
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
