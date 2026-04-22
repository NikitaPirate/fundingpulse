"""OKX exchange adapter.

OKX uses 1-8 hour funding intervals (most contracts are 8h). API limit is 400 records per request.
_FETCH_STEP = 398 hours (400 - 2 safety buffer).
"""

import logging
from typing import Any
from uuid import UUID

from fundingpulse.time import from_unix_milliseconds, utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

logger = logging.getLogger(__name__)


class OkxExchange(BaseExchange):
    """OKX exchange adapter."""

    EXCHANGE_ID = "okx"
    API_ENDPOINT = "https://www.okx.com/api/v5"

    # 400 records max, 1-hour min interval -> 398 hours (400 - 2 safety buffer)
    _FETCH_STEP = 398

    def _format_symbol(self, contract: TrackedContract) -> str:
        return f"{contract.asset_name}-{contract.quote_name}-SWAP"

    async def get_contracts(self) -> list[ContractInfo]:
        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/public/instruments",
            params={"instType": "SWAP"},
        )

        contracts = []
        if response.get("code") == "0" and response.get("data"):
            for instrument in response["data"]:
                if instrument["state"] == "live":
                    # Parse "BTC-USDT-SWAP" format
                    asset_name, quote, _ = instrument["instId"].split("-")
                    contracts.append(
                        ContractInfo(
                            asset_name=asset_name,
                            quote=quote,
                            funding_interval=8,
                            section_name=self.EXCHANGE_ID,
                        )
                    )

        return contracts

    async def _fetch_history(
        self, contract: TrackedContract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/public/funding-rate-history",
            params={
                "instId": symbol,
                # counterintuitive feature of OKX API: "after" and "before" are reversed
                "after": end_ms,
                "before": start_ms,
                "limit": 400,
            },
        )

        points = []
        if response.get("code") == "0" and response.get("data"):
            for raw_record in response["data"]:
                rate = float(raw_record["fundingRate"])
                timestamp = from_unix_milliseconds(int(raw_record["fundingTime"]))
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_single(self, contract: TrackedContract) -> FundingPoint:
        symbol = self._format_symbol(contract)

        response: Any = await self._api_get(
            f"{self.API_ENDPOINT}/public/funding-rate",
            params={"instId": symbol},
        )

        data = response.get("data")
        if not data:
            raise ValueError(f"No funding rate data for {symbol}")

        record = data[0]
        now = utc_now()
        rate = float(record["fundingRate"])
        return FundingPoint(rate=rate, timestamp=now)

    async def fetch_live(self, contracts: list[TrackedContract]) -> dict[UUID, FundingPoint]:
        return await self._fetch_live_parallel(contracts)
