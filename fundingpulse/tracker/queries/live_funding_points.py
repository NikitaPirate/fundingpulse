"""Live funding point query functions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from fundingpulse.models.live_funding_point import LiveFundingPoint


class SQLModelWithTable(SQLModel):
    """SQLModel class with a SQLAlchemy table object."""

    __table__: Any


async def insert_live_funding_points(
    session: AsyncSession,
    records: Iterable[LiveFundingPoint],
) -> int:
    """Insert live funding points idempotently and return the inserted row count."""
    records_list = list(records)
    if not records_list:
        return 0

    model_cls = cast(type[SQLModelWithTable], LiveFundingPoint)
    table = model_cls.__table__
    values = [
        {
            column.key: getattr(record, column.key)
            for column in table.columns
            if hasattr(record, column.key)
        }
        for record in records_list
    ]
    stmt = pg_insert(table).values(values).on_conflict_do_nothing().returning(table.c.contract_id)
    result = await session.execute(stmt)
    inserted = len(result.fetchall())
    await session.flush()
    return inserted
