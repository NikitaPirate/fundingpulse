"""Derive live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class DeriveLiveExchange(BaseLiveExchange):
    """Derive live adapter using the instrument listing endpoint."""

    EXCHANGE_ID = "derive"
    API_ENDPOINT = "https://api.lyra.finance/public"

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}-PERP"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_post(
            f"{self.API_ENDPOINT}/get_all_instruments",
            json={
                "currency": None,
                "expired": True,
                "instrument_type": "perp",
                "page": 1,
                "page_size": 100,
            },
            headers={"Content-Type": "application/json"},
        )
        assert isinstance(response, dict)

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        instruments = response.get("result", {}).get("instruments", [])
        for instrument in instruments:
            perp_details = instrument.get("perp_details")
            if instrument.get("is_active") and perp_details and "funding_rate" in perp_details:
                rates[instrument["instrument_name"]] = FundingPoint(
                    rate=float(perp_details["funding_rate"]),
                    timestamp=now,
                )
        return rates
