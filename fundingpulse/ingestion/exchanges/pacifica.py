"""Pacifica live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class PacificaLiveExchange(BaseLiveExchange):
    """Pacifica live adapter using the prices endpoint."""

    EXCHANGE_ID = "pacifica"
    API_ENDPOINT = "https://api.pacifica.fi/api/v1"

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset_name

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/info/prices")
        assert isinstance(response, dict)
        if not response.get("success") or not response.get("data"):
            return {}

        data = response["data"]
        assert isinstance(data, list)

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        for item in data:
            funding_rate = item.get("funding")
            if funding_rate is not None:
                rates[item["symbol"]] = FundingPoint(
                    rate=float(funding_rate),
                    timestamp=now,
                )
        return rates
