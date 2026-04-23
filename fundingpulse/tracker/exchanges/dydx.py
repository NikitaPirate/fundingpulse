"""dYdX v4 exchange adapter.

dYdX v4 uses 1-hour funding interval. History limit is 1000 records per request.
_FETCH_STEP = 1000 hours (1000 records at 1-hour interval).
"""

import logging

from fundingpulse.models.contract import Contract
from fundingpulse.time import from_unix_milliseconds, from_utc_iso8601, to_iso8601, utc_now
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint

logger = logging.getLogger(__name__)


class DydxExchange(BaseExchange):
    """dYdX v4 exchange adapter."""

    EXCHANGE_ID = "dydx"
    API_ENDPOINT = "https://indexer.dydx.trade/v4"

    # API limit: 1000 records at 1-hour interval = 1000 hours
    _FETCH_STEP = 1000

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset_name}-USD"

    async def get_contracts(self) -> list[ExchangeContractListing]:
        response = await self._api_get(
            f"{self.API_ENDPOINT}/perpetualMarkets",
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        contracts = []
        markets = response.get("markets", {})

        for ticker, _ in markets.items():
            if "-" in ticker and ticker.endswith("-USD"):
                asset_name = ticker.removesuffix("-USD")
                contracts.append(
                    ExchangeContractListing(
                        asset_name=asset_name,
                        quote_name="USD",
                        funding_interval=1,
                        section_name=self.EXCHANGE_ID,
                    )
                )

        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        # dYdX uses ISO8601 format, not milliseconds
        end_time_iso = to_iso8601(from_unix_milliseconds(end_ms))

        response = await self._api_get(
            f"{self.API_ENDPOINT}/historicalFunding/{symbol}",
            params={
                "effectiveBeforeOrAt": end_time_iso,
            },
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        points = []
        raw_records = response.get("historicalFunding", [])

        if raw_records:
            for raw_record in raw_records:
                rate = float(raw_record["rate"])
                timestamp = from_utc_iso8601(raw_record["effectiveAt"])
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response = await self._api_get(
            f"{self.API_ENDPOINT}/perpetualMarkets",
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        now = utc_now()
        rates = {}
        markets = response.get("markets", {})

        for ticker, market in markets.items():
            if "-" in ticker and "nextFundingRate" in market:
                rates[ticker] = FundingPoint(
                    rate=float(market["nextFundingRate"]),
                    timestamp=now,
                )

        return rates
