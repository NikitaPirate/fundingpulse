"""KuCoin live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class KucoinLiveExchange(BaseLiveExchange):
    """KuCoin live adapter using the active contracts endpoint."""

    EXCHANGE_ID = "kucoin"
    API_ENDPOINT = "https://api-futures.kucoin.com"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}{contract.quote_name}M"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/api/v1/contracts/active")
        assert isinstance(response, dict)
        if response.get("code") != "200000":
            raise RuntimeError(f"KuCoin API error: {response}")

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        for contract in response.get("data", []):
            if contract["status"] != "Open":
                continue
            if not contract.get("fundingRateGranularity"):
                continue
            funding_fee_rate = contract.get("fundingFeeRate")
            if funding_fee_rate is not None:
                rates[contract["symbol"]] = FundingPoint(
                    rate=float(funding_fee_rate),
                    timestamp=now,
                )
        return rates
