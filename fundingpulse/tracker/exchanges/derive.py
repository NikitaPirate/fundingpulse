"""Derive exchange adapter.

Derive (Lyra Finance) uses 1-hour period for history API. API allows fetching
30 days of history per request (start timestamp restricted to at most 30 days ago).
_FETCH_STEP = 720 hours (30 days × 24 hours).
"""

import logging
from datetime import datetime

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

logger = logging.getLogger(__name__)


class DeriveExchange(BaseExchange):
    """Derive exchange adapter."""

    EXCHANGE_ID = "derive"
    API_ENDPOINT = "https://api.lyra.finance/public"

    # API allows 30 days per request: 30 days × 24 hours = 720 hours
    _FETCH_STEP = 720

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset.name}-PERP"

    async def get_contracts(self) -> list[ContractInfo]:
        all_instruments = []
        page = 1

        while True:
            response = await self._api_post(
                f"{self.API_ENDPOINT}/get_all_instruments",
                json={
                    "currency": None,
                    "expired": True,
                    "instrument_type": "perp",
                    "page": page,
                    "page_size": 100,
                },
                headers={"Content-Type": "application/json"},
            )

            assert isinstance(response, dict)

            all_instruments.extend(response.get("result", {}).get("instruments", []))

            pagination = response.get("result", {}).get("pagination", {})
            num_pages = pagination.get("num_pages", 1)

            if page >= num_pages:
                break
            page += 1

        contracts = []
        for instrument in all_instruments:
            if instrument.get("is_active"):
                instrument_name = instrument["instrument_name"]
                asset_name = instrument_name.replace("-PERP", "")

                contracts.append(
                    ContractInfo(
                        asset_name=asset_name,
                        quote="USD",
                        # Derive settles funding continuously, but history API uses period=3600
                        funding_interval=1,
                        section_name=self.EXCHANGE_ID,
                    )
                )

        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response = await self._api_post(
            f"{self.API_ENDPOINT}/get_funding_rate_history",
            json={
                "instrument_name": symbol,
                "period": 3600,
                "end_timestamp": end_ms,
            },
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        points = []
        result = response.get("result")
        if result and "funding_rate_history" in result:
            for raw_record in result["funding_rate_history"]:
                rate = float(raw_record["funding_rate"])
                timestamp = datetime.fromtimestamp(raw_record["timestamp"] / 1000.0)
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response = await self._api_post(
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

        now = datetime.now()
        rates = {}
        instruments = response.get("result", {}).get("instruments", [])

        for instrument in instruments:
            if (
                instrument.get("is_active")
                and "perp_details" in instrument
                and instrument["perp_details"]
                and "funding_rate" in instrument["perp_details"]
            ):
                instrument_name = instrument["instrument_name"]
                funding_rate = float(instrument["perp_details"]["funding_rate"])
                rates[instrument_name] = FundingPoint(rate=funding_rate, timestamp=now)

        return rates
