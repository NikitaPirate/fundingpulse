"""Pacifica exchange adapter.

Pacifica uses 1-hour funding interval. API limit is 4000 records per request.
Uses cursor-based pagination (next_cursor, has_more).
_FETCH_STEP = 4000 hours (4000 records, 1-hour interval).
"""

import logging
from datetime import datetime
from typing import Any

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

logger = logging.getLogger(__name__)


class PacificaExchange(BaseExchange):
    """Pacifica exchange adapter."""

    EXCHANGE_ID = "pacifica"
    API_ENDPOINT = "https://api.pacifica.fi/api/v1"

    # 4000 records max, 1-hour interval -> 4000 hours
    _FETCH_STEP = 4000

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset.name

    async def get_contracts(self) -> list[ContractInfo]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/info")

        assert isinstance(response, dict)

        if not response.get("success") or not response.get("data"):
            return []

        data = response["data"]
        assert isinstance(data, list)

        contracts = []
        for item in data:
            symbol = item["symbol"]
            contracts.append(
                ContractInfo(
                    asset_name=symbol,
                    quote="USD",
                    funding_interval=1,
                    section_name=self.EXCHANGE_ID,
                )
            )

        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        points = []
        cursor = None

        while True:
            params = {"symbol": symbol, "limit": 1000}

            if cursor:
                params["cursor"] = cursor

            response: Any = await self._api_get(
                f"{self.API_ENDPOINT}/funding_rate/history",
                params=params,
            )

            assert isinstance(response, dict)

            if not response.get("success") or not response.get("data"):
                break

            records = response["data"]
            assert isinstance(records, list)

            # Parse records (DESC order: newest first)
            batch_points = []
            for raw_record in records:
                timestamp_ms = raw_record["created_at"]

                # Skip if outside our range
                if timestamp_ms > end_ms:
                    continue
                if timestamp_ms < start_ms:
                    break

                rate = float(raw_record["funding_rate"])
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
                batch_points.append(FundingPoint(rate=rate, timestamp=timestamp))

            points.extend(batch_points)

            # Check pagination
            has_more = response.get("has_more", False)
            next_cursor = response.get("next_cursor")

            if not has_more or not next_cursor:
                break

            cursor = next_cursor

            # Safety check
            if len(points) >= 4000:
                break

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response: Any = await self._api_get(f"{self.API_ENDPOINT}/info/prices")

        assert isinstance(response, dict)

        if not response.get("success") or not response.get("data"):
            return {}

        now = datetime.now()
        rates = {}

        data = response["data"]
        assert isinstance(data, list)

        for item in data:
            symbol = item["symbol"]
            funding_rate = item.get("funding")

            if funding_rate is not None:
                rate = float(funding_rate)
                rates[symbol] = FundingPoint(rate=rate, timestamp=now)

        return rates
