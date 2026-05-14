"""Binance COIN-M live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class BinanceCoinmLiveExchange(BaseLiveExchange):
    """Binance COIN-M live adapter using the batch premium index endpoint."""

    EXCHANGE_ID = "binance_coin-m"
    API_ENDPOINT = "https://dapi.binance.com/dapi"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}{contract.quote_name}_PERP"

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
