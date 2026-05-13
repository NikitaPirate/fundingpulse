"""OKX live funding adapter."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class OkxLiveExchange(BaseLiveExchange):
    """OKX live adapter using parallel per-contract requests."""

    EXCHANGE_ID = "okx"
    API_ENDPOINT = "https://www.okx.com/api/v5"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}-{contract.quote_name}-SWAP"

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        symbol = self._format_symbol(contract)
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/public/funding-rate",
            params={"instId": symbol},
        )

        data = response.get("data")
        if not data:
            raise ValueError(f"No funding rate data for {symbol}")

        return FundingPoint(
            rate=float(data[0]["fundingRate"]),
            timestamp=utc_now(),
        )

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        return await self._fetch_live_parallel(contracts)
