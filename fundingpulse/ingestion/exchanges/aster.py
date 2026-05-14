"""Aster live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class AsterLiveExchange(BaseLiveExchange):
    """Aster live adapter using the batch premium index endpoint."""

    EXCHANGE_ID = "aster"
    API_ENDPOINT = "https://fapi.asterdex.com/fapi"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}{contract.quote_name}"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/v1/premiumIndex")
        assert isinstance(response, list), "premiumIndex must return list"

        now = utc_now()
        return {
            market["symbol"]: FundingPoint(
                rate=float(market["lastFundingRate"]),
                timestamp=now,
            )
            for market in response
        }
