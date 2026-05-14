"""Paradex live funding adapter."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class ParadexLiveExchange(BaseLiveExchange):
    """Paradex live adapter using the most recent funding record per contract."""

    EXCHANGE_ID = "paradex"
    API_ENDPOINT = "https://api.prod.paradex.trade/v1"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}-USD-PERP"

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        symbol = self._format_symbol(contract)
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/funding/data",
            params={
                "market": symbol,
                "page_size": 1,
            },
        )
        assert isinstance(response, dict)

        data = response["results"]
        if not data:
            raise ValueError(f"No funding rate data for {symbol}")

        raw_rate = float(data[0]["funding_rate"])
        return FundingPoint(
            rate=raw_rate / 8,
            timestamp=utc_now(),
        )

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        return await self._fetch_live_parallel(contracts)
