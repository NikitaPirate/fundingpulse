"""Periodic asset market-cap ranking update from CoinGecko."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.models.asset import Asset
from fundingpulse.tracker.db import SessionFactory
from fundingpulse.tracker.infrastructure import http_client

logger = logging.getLogger(__name__)

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


async def update_rankings(session_factory: SessionFactory) -> None:
    """Fetch top-250 coins from CoinGecko and update asset.market_cap_rank."""
    try:
        coin_data = await _fetch_coingecko_top250()
        if not coin_data:
            logger.warning("No data received from CoinGecko API")
            return

        symbol_to_rank: dict[str, int] = {
            coin["symbol"].upper(): coin["market_cap_rank"]
            for coin in coin_data
            if coin.get("symbol") and coin.get("market_cap_rank")
        }

        async with session_factory.begin() as session:
            assets = await _get_all_assets(session)
            matched = 0
            for asset in assets:
                rank = symbol_to_rank.get(asset.name.upper())
                if rank != asset.market_cap_rank:
                    await session.execute(
                        update(Asset)
                        .where(Asset.name == asset.name)  # type: ignore[arg-type]
                        .values(market_cap_rank=rank)
                    )
                if rank is not None:
                    matched += 1

            logger.info(
                "Asset rankings updated — matched %d/%d assets",
                matched,
                len(assets),
            )

    except Exception:
        logger.exception("Failed to update asset rankings")
        raise


async def _get_all_assets(session: AsyncSession) -> list[Asset]:
    from sqlmodel import select

    result = await session.execute(select(Asset))
    return list(result.scalars().all())


async def _fetch_coingecko_top250() -> list[dict[str, Any]]:
    """Fetch top 250 cryptocurrencies by market cap."""
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": "250",
        "page": "1",
        "sparkline": "false",
    }
    data = await http_client.get(COINGECKO_MARKETS_URL, params=params)
    if not isinstance(data, list):
        logger.error("Unexpected CoinGecko response format: %s", type(data))
        return []
    logger.info("Fetched %d coins from CoinGecko", len(data))
    return data
