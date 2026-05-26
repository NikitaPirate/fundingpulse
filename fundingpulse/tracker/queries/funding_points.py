"""Funding point query functions."""

from collections.abc import Iterable
from typing import Any, cast
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import asc, desc
from sqlmodel import SQLModel, col, select

from fundingpulse.models.historical_funding_point import HistoricalFundingPoint


class SQLModelWithTable(SQLModel):
    """SQLModel class with a SQLAlchemy table object."""

    __table__: Any


async def get_oldest_for_contract(
    session: AsyncSession, contract_id: UUID
) -> HistoricalFundingPoint | None:
    stmt = (
        select(HistoricalFundingPoint)
        .where(col(HistoricalFundingPoint.contract_id) == contract_id)
        .order_by(asc(col(HistoricalFundingPoint.timestamp)))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def insert_historical_funding_points(
    session: AsyncSession,
    records: Iterable[HistoricalFundingPoint],
) -> int:
    """Insert historical funding points idempotently and return inserted row count."""
    records_list = list(records)
    if not records_list:
        return 0

    model_cls = cast(type[SQLModelWithTable], HistoricalFundingPoint)
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


async def get_newest_for_contract(
    session: AsyncSession, contract_id: UUID
) -> HistoricalFundingPoint | None:
    stmt = (
        select(HistoricalFundingPoint)
        .where(col(HistoricalFundingPoint.contract_id) == contract_id)
        .order_by(desc(col(HistoricalFundingPoint.timestamp)))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
