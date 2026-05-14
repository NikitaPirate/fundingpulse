"""Extended live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class ExtendedLiveExchange(BaseLiveExchange):
    """Extended live adapter using the markets endpoint."""

    EXCHANGE_ID = "extended"
    API_ENDPOINT = "https://api.starknet.extended.exchange"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}-{contract.quote_name}"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/api/v1/info/markets")
        assert isinstance(response, dict)
        if response.get("status") != "OK":
            raise RuntimeError(f"Extended API error: {response}")

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        for market in response.get("data", []):
            if market.get("status") != "ACTIVE":
                continue
            funding_rate = market.get("marketStats", {}).get("fundingRate")
            if funding_rate is not None:
                rates[market.get("name", "")] = FundingPoint(
                    rate=float(funding_rate),
                    timestamp=now,
                )
        return rates
