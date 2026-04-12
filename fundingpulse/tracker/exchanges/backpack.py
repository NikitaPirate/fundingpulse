"""Backpack exchange adapter.

ALL contracts use 1-hour funding interval (verified across 73 contracts).
API has NO record limit.
Uses unique backward pagination from present time (offset-based, not startTime/endTime).
offset=0 is future/un-calculated; offset=1 is most recent CALCULATED funding.
_FETCH_STEP = 1000 hours (no API limit, convenient batch size).
"""

import logging
from datetime import datetime

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

logger = logging.getLogger(__name__)


class BackpackExchange(BaseExchange):
    """Backpack exchange adapter."""

    EXCHANGE_ID = "backpack"
    API_ENDPOINT = "https://api.backpack.exchange/api/v1"
    _FETCH_STEP = 1000

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset.name}_{contract.quote_name}_PERP_{contract.funding_interval}"

    async def get_contracts(self) -> list[ContractInfo]:
        response = await self._api_get(f"{self.API_ENDPOINT}/markets")

        assert isinstance(response, list)

        contracts = []
        for market in response:
            if market["marketType"] == "PERP":
                symbol = market["symbol"]
                asset_name, quote_name, _ = symbol.split("_")
                funding_interval = market["fundingInterval"] / (1000 * 60 * 60)

                contracts.append(
                    ContractInfo(
                        asset_name=asset_name,
                        quote=quote_name,
                        funding_interval=funding_interval,
                        section_name=self.EXCHANGE_ID,
                    )
                )

        return contracts

    async def fetch_history_before(
        self, contract: Contract, before_timestamp: datetime | None
    ) -> list[FundingPoint]:
        # Remove interval suffix for API (accepts both formats)
        api_symbol = self._format_symbol(contract).rsplit("_", 1)[0]
        funding_interval = contract.funding_interval
        end_time = before_timestamp or datetime.now()

        now = datetime.now()
        # offset=1 skips future record, starts from most recent calculated
        offset_end = 1 + int((now - end_time).total_seconds() / (funding_interval * 3600))
        offset_start = offset_end + (self._FETCH_STEP // funding_interval)

        limit = offset_start - offset_end
        if limit < 1:
            return []

        response = await self._api_get(
            f"{self.API_ENDPOINT}/fundingRates",
            params={"symbol": api_symbol, "limit": limit, "offset": offset_end},
        )

        assert isinstance(response, list)

        points = []
        for raw_record in response:
            rate = float(raw_record["fundingRate"])
            timestamp = datetime.fromisoformat(raw_record["intervalEndTimestamp"])
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def fetch_history_after(
        self, contract: Contract, after_timestamp: datetime
    ) -> list[FundingPoint]:
        api_symbol = self._format_symbol(contract).rsplit("_", 1)[0]
        funding_interval = contract.funding_interval

        now = datetime.now()
        # Start from offset=1 (most recent calculated), go back to after_timestamp
        offset_end = 1
        offset_start = 1 + int(
            (now - after_timestamp).total_seconds() // (funding_interval * 3600)
        )

        limit = offset_start - offset_end
        if limit < 1:
            return []

        response = await self._api_get(
            f"{self.API_ENDPOINT}/fundingRates",
            params={"symbol": api_symbol, "limit": limit, "offset": offset_end},
        )

        assert isinstance(response, list)

        points = []
        for raw_record in response:
            timestamp = datetime.fromisoformat(raw_record["intervalEndTimestamp"])
            if timestamp <= after_timestamp:
                continue
            rate = float(raw_record["fundingRate"])
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        start_time = datetime.fromtimestamp(start_ms / 1000)
        end_time = datetime.fromtimestamp(end_ms / 1000)

        api_symbol = self._format_symbol(contract).rsplit("_", 1)[0]
        funding_interval = contract.funding_interval

        now = datetime.now()
        offset_end = 1 + int((now - end_time).total_seconds() / (funding_interval * 3600))
        offset_start = 1 + int((now - start_time).total_seconds() // (funding_interval * 3600))

        limit = offset_start - offset_end
        if limit < 1:
            return []

        response = await self._api_get(
            f"{self.API_ENDPOINT}/fundingRates",
            params={"symbol": api_symbol, "limit": limit, "offset": offset_end},
        )

        assert isinstance(response, list)

        points = []
        for raw_record in response:
            rate = float(raw_record["fundingRate"])
            timestamp = datetime.fromisoformat(raw_record["intervalEndTimestamp"])
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        api_symbol = self._format_symbol(contract).rsplit("_", 1)[0]

        response = await self._api_get(
            f"{self.API_ENDPOINT}/fundingRates",
            params={"symbol": api_symbol, "limit": 1},
        )

        assert isinstance(response, list)

        if not response:
            raise ValueError(f"No funding rate data for {api_symbol}")

        raw_record = response[0]
        rate = float(raw_record["fundingRate"])
        return FundingPoint(rate=rate, timestamp=datetime.now())

    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        return await self._fetch_live_parallel(contracts)
