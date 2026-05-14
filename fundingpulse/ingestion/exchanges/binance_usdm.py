"""Binance USD-M live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class BinanceUsdmLiveExchange(BaseLiveExchange):
    """Binance USD-M live adapter using the batch premium index endpoint."""

    EXCHANGE_ID = "binance_usd-m"
    API_ENDPOINT = "https://fapi.binance.com/fapi"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}{contract.quote_name}"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/v1/premiumIndex")
        now = utc_now()
        return {
            item["symbol"]: FundingPoint(
                rate=float(item["lastFundingRate"]),
                timestamp=now,
            )
            for item in response
        }
