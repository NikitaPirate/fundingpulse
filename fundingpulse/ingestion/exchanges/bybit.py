"""Bybit live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class BybitLiveExchange(BaseLiveExchange):
    """Bybit live adapter using the batch tickers endpoint."""

    EXCHANGE_ID = "bybit"
    API_ENDPOINT = "https://api.bybit.com"

    _SUFFIXES = {"USDT": "USDT", "USDC": "PERP"}

    def _format_symbol(self, contract: Contract) -> str:
        suffix = self._SUFFIXES.get(contract.quote_name, contract.quote_name)
        return f"{contract.asset_name}{suffix}"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/v5/market/tickers",
            params={"category": "linear"},
        )

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        for record in response["result"]["list"]:
            funding_rate = record.get("fundingRate", "")
            if not funding_rate:
                continue

            rates[record["symbol"]] = FundingPoint(
                rate=float(funding_rate),
                timestamp=now,
            )
        return rates
