"""Funding point query functions."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import asc, desc
from sqlmodel import col, select

from fundingpulse.models.historical_funding_point import HistoricalFundingPoint


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
