"""Bybit exchange adapter.

Bybit has both USDT and USDC perpetuals. API limit is 200 records per request.
Minimal funding interval is 1 hour.
_FETCH_STEP = 198 hours (200 - 2 safety buffer).

Live rates use batch API: single /v5/market/tickers request fetches all contracts.
"""

import logging
from typing import Any

from fundingpulse.time import from_unix_milliseconds, utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint

logger = logging.getLogger(__name__)


class BybitExchange(BaseExchange):
    """Bybit exchange adapter."""

    EXCHANGE_ID = "bybit"
    API_ENDPOINT = "https://api.bybit.com"

    # 200 records max, 1-hour min interval -> 198 hours (200 - 2 safety buffer)
    _FETCH_STEP = 198

    _SUFFIXES = {"USDT": "USDT", "USDC": "PERP"}

    def _format_symbol(self, contract: TrackedContract) -> str:
        suffix = self._SUFFIXES.get(contract.quote_name, contract.quote_name)
        return f"{contract.asset_name}{suffix}"

    async def get_contracts(self) -> list[ExchangeContractListing]:
        all_contracts = []
        cursor = None

        while True:
            params = {"category": "linear"}
            if cursor:
                params["cursor"] = cursor

            response: Any = await self._api_get(
                f"{self.API_ENDPOINT}/v5/market/instruments-info", params=params
            )

            all_contracts.extend(response["result"]["list"])

            cursor = response["result"].get("nextPageCursor")
            if not cursor:
                break

        contracts = []
        for contract in all_contracts:
            if contract["contractType"] == "LinearPerpetual":
                contracts.append(
                    ExchangeContractListing(
                        asset_name=contract["baseCoin"],
                        quote_name=contract["quoteCoin"],
                        funding_interval=int(contract["fundingInterval"] / 60),
                        section_name=self.EXCHANGE_ID,
                    )
                )

        return contracts

    async def _fetch_history(
        self, contract: TrackedContract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/v5/market/funding/history",
            params={
                "symbol": symbol,
                "category": "linear",
                "startTime": start_ms,
                "endTime": end_ms,
            },
        )

        points = []
        raw_records = response.get("result", {}).get("list", [])
        if raw_records:
            for raw_record in raw_records:
                rate = float(raw_record["fundingRate"])
                timestamp = from_unix_milliseconds(int(raw_record["fundingRateTimestamp"]))
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/v5/market/tickers",
            params={"category": "linear"},
        )

        now = utc_now()
        rates = {}

        for record in response["result"]["list"]:
            funding_rate_str = record.get("fundingRate", "")
            if not funding_rate_str:
                continue

            symbol = record["symbol"]
            rate = float(funding_rate_str)
            rates[symbol] = FundingPoint(rate=rate, timestamp=now)

        return rates
