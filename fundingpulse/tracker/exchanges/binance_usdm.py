"""Binance USD-M exchange adapter.

Binance USDⓈ-M has mixed funding intervals (1-8 hours). API limit is 1000 records.
Minimum interval is 1 hour.
_FETCH_STEP = 1000 hours.
"""

import asyncio
import logging
from typing import Any

from fundingpulse.time import from_unix_milliseconds, utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint

logger = logging.getLogger(__name__)


class BinanceUsdmExchange(BaseExchange):
    """Binance USD-M exchange adapter."""

    EXCHANGE_ID = "binance_usd-m"
    API_ENDPOINT = "https://fapi.binance.com/fapi"

    # 1000 records max, 1-hour min interval -> 1000 hours
    _FETCH_STEP = 1000

    def _format_symbol(self, contract: TrackedContract) -> str:
        return f"{contract.asset_name}{contract.quote_name}"

    async def get_contracts(self) -> list[ExchangeContractListing]:
        exchange_response: Any
        funding_response: Any
        exchange_response, funding_response = await asyncio.gather(
            self._api_get(f"{self.API_ENDPOINT}/v1/exchangeInfo"),
            self._api_get(f"{self.API_ENDPOINT}/v1/fundingInfo"),
        )

        contracts = []
        funding_intervals = {
            item["symbol"]: item["fundingIntervalHours"] for item in funding_response
        }

        for instrument in exchange_response["symbols"]:
            if instrument["contractType"] == "PERPETUAL":
                funding_interval = funding_intervals.get(instrument["pair"], 8)

                contracts.append(
                    ExchangeContractListing(
                        asset_name=instrument["baseAsset"],
                        quote_name=instrument["quoteAsset"],
                        funding_interval=funding_interval,
                        section_name=self.EXCHANGE_ID,
                    )
                )

        return contracts

    async def _fetch_history(
        self, contract: TrackedContract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/v1/fundingRate",
            params={
                "symbol": symbol,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            },
        )

        points = []
        if response:
            for raw_record in response:
                rate = float(raw_record["fundingRate"])
                timestamp = from_unix_milliseconds(raw_record["fundingTime"])
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/v1/premiumIndex")

        now = utc_now()
        rates = {}
        for item in response:
            symbol = item["symbol"]
            rate = float(item["lastFundingRate"])
            rates[symbol] = FundingPoint(rate=rate, timestamp=now)

        return rates
