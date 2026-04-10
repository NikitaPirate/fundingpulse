"""Binance USD-M exchange adapter.

Binance USDⓈ-M has mixed funding intervals (1-8 hours). API limit is 1000 records.
Minimum interval is 1 hour.
_FETCH_STEP = 1000 hours.
"""

import logging
from datetime import datetime
from typing import Any

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint
from fundingpulse.tracker.infrastructure import http_client

logger = logging.getLogger(__name__)


class BinanceUsdmExchange(BaseExchange):
    """Binance USD-M exchange adapter."""

    EXCHANGE_ID = "binance_usd-m"
    API_ENDPOINT = "https://fapi.binance.com/fapi"

    # 1000 records max, 1-hour min interval -> 1000 hours
    _FETCH_STEP = 1000

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset.name}{contract.quote_name}"

    async def get_contracts(self) -> list[ContractInfo]:
        exchange_response: Any = await http_client.get(f"{self.API_ENDPOINT}/v1/exchangeInfo")
        funding_response: Any = await http_client.get(f"{self.API_ENDPOINT}/v1/fundingInfo")

        contracts = []
        funding_intervals = {
            item["symbol"]: item["fundingIntervalHours"] for item in funding_response
        }

        for instrument in exchange_response["symbols"]:
            if instrument["contractType"] == "PERPETUAL":
                funding_interval = funding_intervals.get(instrument["pair"], 8)

                contracts.append(
                    ContractInfo(
                        asset_name=instrument["baseAsset"],
                        quote=instrument["quoteAsset"],
                        funding_interval=funding_interval,
                        section_name=self.EXCHANGE_ID,
                    )
                )

        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response: Any = await http_client.get(
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
                timestamp = datetime.fromtimestamp(raw_record["fundingTime"] / 1000.0)
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_all_rates(self) -> dict[str, FundingPoint]:
        response: Any = await http_client.get(f"{self.API_ENDPOINT}/v1/premiumIndex")

        now = datetime.now()
        rates = {}
        for item in response:
            symbol = item["symbol"]
            rate = float(item["lastFundingRate"])
            rates[symbol] = FundingPoint(rate=rate, timestamp=now)

        return rates

    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        symbol_to_contract = {self._format_symbol(c): c for c in contracts}
        all_rates = await self._fetch_all_rates()

        return {
            symbol_to_contract[symbol]: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract
        }
