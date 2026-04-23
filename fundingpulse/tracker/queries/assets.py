"""Asset query functions."""

from collections.abc import Sequence

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from fundingpulse.models.asset import Asset


async def get_all(session: AsyncSession) -> Sequence[Asset]:
    """Return all asset rows."""
    result = await session.execute(select(Asset))
    return result.scalars().all()


async def update_market_cap_rank(
    session: AsyncSession,
    asset_name: str,
    market_cap_rank: int | None,
) -> None:
    """Update one asset's market-cap rank."""
    await session.execute(
        update(Asset).where(col(Asset.name) == asset_name).values(market_cap_rank=market_cap_rank)
    )
