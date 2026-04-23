import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.testing.helpers.data_helpers import get_or_create_asset
from fundingpulse.tracker.queries import assets as asset_queries


@pytest.mark.asyncio
async def test_update_market_cap_rank_updates_asset(
    db_session: AsyncSession,
) -> None:
    asset = await get_or_create_asset(db_session, "BTC")

    await asset_queries.update_market_cap_rank(db_session, asset.name, 1)
    await db_session.commit()
    await db_session.refresh(asset)

    assert asset.market_cap_rank == 1


@pytest.mark.asyncio
async def test_get_all_returns_asset_rows(
    db_session: AsyncSession,
) -> None:
    asset = await get_or_create_asset(db_session, "ETH")

    rows = await asset_queries.get_all(db_session)

    assert any(row.name == asset.name for row in rows)
