"""Backpack live funding adapter."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class BackpackLiveExchange(BaseLiveExchange):
    """Backpack live adapter using per-contract funding rate requests."""

    EXCHANGE_ID = "backpack"
    API_ENDPOINT = "https://api.backpack.exchange/api/v1"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}_{contract.quote_name}_PERP_{contract.funding_interval}"

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        api_symbol = self._format_symbol(contract).rsplit("_", 1)[0]
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/fundingRates",
            params={"symbol": api_symbol, "limit": 1},
        )
        assert isinstance(response, list)
        if not response:
            raise ValueError(f"No funding rate data for {api_symbol}")

        raw_record = response[0]
        return FundingPoint(
            rate=float(raw_record["fundingRate"]),
            timestamp=utc_now(),
        )

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        return await self._fetch_live_parallel(contracts)
