"""dYdX live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class DydxLiveExchange(BaseLiveExchange):
    """dYdX live adapter using the perpetual markets endpoint."""

    EXCHANGE_ID = "dydx"
    API_ENDPOINT = "https://indexer.dydx.trade/v4"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}-USD"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/perpetualMarkets",
            headers={"Content-Type": "application/json"},
        )
        assert isinstance(response, dict)

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        for ticker, market in response.get("markets", {}).items():
            if "-" in ticker and "nextFundingRate" in market:
                rates[ticker] = FundingPoint(
                    rate=float(market["nextFundingRate"]),
                    timestamp=now,
                )
        return rates
