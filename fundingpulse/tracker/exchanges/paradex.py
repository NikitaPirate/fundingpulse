"""Paradex exchange adapter.

Paradex uses 1-hour funding interval with 8-hour funding period.
API returns funding rate updates every ~5 seconds (720 records/hour).
API limit is 5000 records per request.
_FETCH_STEP = 6 hours = 4320 records (5000 limit - safety buffer).

**Unique Characteristics:**
1. High-frequency updates: ~5 seconds between records (not hourly like most exchanges)
2. 8-hour funding period: API returns raw rates, must divide by 8 for hourly rate
3. Aggregation required: Must average all 5-second records in an hour, then divide by 8
4. Cache optimization: Live collector runs every minute, keeping ~60 records/hour in memory

**Fetching Strategy:**
- fetch_history_before: Batch 6 hours per request (4320 records avg)
- fetch_history_after: Check live cache first (50+ records = use average), else fetch from API
- fetch_live: Individual requests (no batch API), stores in cache for fetch_after

**Rate Calculation:**
1. Fetch all records for the hour from API (or use cached live records)
2. Calculate average: sum(all_rates) / count
3. Divide by 8: API returns 8-hour period rates, we need hourly
4. Result is hourly funding rate at the end of the hour

**Example:**
- Hour: 14:00-15:00
- API returns 720 records (1 every 5 seconds)
- Raw rates range: 0.0001-0.0003 (8-hour cumulative rates)
- Average: 0.0002
- Hourly rate: 0.0002 / 8 = 0.000025 (0.0025%)
- Timestamp: 15:00:00 (end of hour)
"""

import asyncio
import logging
from datetime import timedelta

from fundingpulse.models.contract import Contract
from fundingpulse.time import (
    UtcDateTime,
    from_unix_milliseconds,
    start_of_hour,
    to_unix_milliseconds,
    utc_now,
)
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

logger = logging.getLogger(__name__)


class ParadexExchange(BaseExchange):
    """Paradex exchange adapter with high-frequency funding aggregation."""

    EXCHANGE_ID = "paradex"
    API_ENDPOINT = "https://api.prod.paradex.trade/v1"

    # 6 hours * 720 records/hour = 4320 records (safely under 5000 limit)
    _FETCH_STEP = 6

    def __init__(self, semaphore: asyncio.Semaphore | None = None) -> None:
        super().__init__(semaphore)
        # Live cache: {contract_id: {hour_start_ms: [rates]}}
        # Stores live funding records collected every minute for fetch_after optimization
        # Cache entries are automatically removed via pop() when used in fetch_history_after
        self._live_cache: dict[str, dict[int, list[float]]] = {}

    def _format_symbol(self, contract: Contract) -> str:
        return f"{contract.asset.name}-USD-PERP"

    async def get_contracts(self) -> list[ContractInfo]:
        response = await self._api_get(f"{self.API_ENDPOINT}/markets")

        assert isinstance(response, dict)
        markets = response["results"]

        contracts = []
        for market in markets:
            # Paradex perpetuals have asset_kind = "PERP"
            if market["asset_kind"] != "PERP":
                continue

            # Symbol format: BTC-USD-PERP
            symbol = market["symbol"]
            if not symbol.endswith("-USD-PERP"):
                continue

            asset_name = market["base_currency"]

            contracts.append(
                ContractInfo(
                    asset_name=asset_name,
                    quote="USD",
                    funding_interval=1,  # We aggregate to 1-hour intervals
                    section_name=self.EXCHANGE_ID,
                )
            )

        return contracts

    async def fetch_history_before(
        self, contract: Contract, before_timestamp: UtcDateTime | None
    ) -> list[FundingPoint]:
        """Fetch historical funding points before timestamp.

        Optimized for Paradex high-frequency data:
        - Fetches 6-hour batches (4320 records avg, under 5000 API limit)
        - Aggregates 5-second records to hourly averages
        - Divides by 8 to convert 8-hour period rates to hourly

        Args:
            contract: Contract to fetch history for
            before_timestamp: Fetch data before this time (None = from now)

        Returns:
            List of hourly FundingPoint objects in chronological order
        """
        end_time = before_timestamp or utc_now()

        # Round down to hour boundary for clean hour alignment
        end_time = start_of_hour(end_time)
        start_time = end_time - timedelta(hours=self._FETCH_STEP)

        start_ms = to_unix_milliseconds(start_time)
        end_ms = to_unix_milliseconds(end_time)

        symbol = self._format_symbol(contract)

        logger.debug(
            f"Fetching history for {self.EXCHANGE_ID}/{symbol} from {start_time} to {end_time}"
        )

        response = await self._api_get(
            f"{self.API_ENDPOINT}/funding/data",
            params={
                "market": symbol,
                "start_at": start_ms,
                "end_at": end_ms,
                "page_size": 5000,
            },
        )

        assert isinstance(response, dict)
        raw_records = response["results"]

        if not raw_records:
            logger.debug(f"No funding records for {self.EXCHANGE_ID}/{symbol}")
            return []

        # Group records by hour and aggregate
        # API returns ~720 records/hour (1 every 5 seconds)
        # We need to average each hour, then divide by 8 (8-hour funding period)
        hourly_points = self._aggregate_to_hourly(raw_records)

        logger.debug(
            f"Fetched {len(raw_records)} raw records, "
            f"aggregated to {len(hourly_points)} hourly points "
            f"for {self.EXCHANGE_ID}/{symbol}"
        )

        return hourly_points

    async def fetch_history_after(
        self, contract: Contract, after_timestamp: UtcDateTime
    ) -> list[FundingPoint]:
        """Fetch funding points after timestamp using live cache optimization.

        Strategy:
        1. Split time range into hours
        2. For each hour, check live cache (collected by fetch_live every minute)
        3. If cache has 50+ records: use cached average
        4. If cache has <50 records: fetch from API (same logic as fetch_history_before)

        This optimization works because live collector runs every minute,
        accumulating ~60 records/hour. Using cached data avoids API calls for
        recent hours where we already have sufficient data.

        Args:
            contract: Contract to fetch history for
            after_timestamp: Fetch data after this time

        Returns:
            List of hourly FundingPoint objects in chronological order
        """
        now = utc_now()
        start = after_timestamp
        contract_id = str(contract.id)

        # Align to hour boundaries
        start = start_of_hour(start)
        now = start_of_hour(now)

        # Generate list of hours to fetch
        hours_to_fetch = []
        current = start + timedelta(hours=1)  # Start with next hour after after_timestamp
        while current <= now:
            hours_to_fetch.append(current)
            current += timedelta(hours=1)

        if not hours_to_fetch:
            return []

        symbol = self._format_symbol(contract)
        all_points = []

        for hour_end in hours_to_fetch:
            hour_start = hour_end - timedelta(hours=1)
            hour_start_ms = to_unix_milliseconds(hour_start)

            # Check live cache and remove entry (pop) - cache auto-cleans when used
            cached_rates = self._live_cache.get(contract_id, {}).pop(hour_start_ms, None)

            if cached_rates and len(cached_rates) >= 50:
                # Use cached average
                avg_cached = sum(cached_rates) / len(cached_rates)
                hourly_rate = avg_cached / 8  # Convert 8-hour period to hourly

                all_points.append(FundingPoint(rate=hourly_rate, timestamp=hour_end))

                logger.debug(
                    f"Using cached average for {self.EXCHANGE_ID}/{symbol} "
                    f"hour {hour_end} ({len(cached_rates)} records)"
                )
            else:
                # Fetch from API
                hour_end_ms = to_unix_milliseconds(hour_end)

                response = await self._api_get(
                    f"{self.API_ENDPOINT}/funding/data",
                    params={
                        "market": symbol,
                        "start_at": hour_start_ms,
                        "end_at": hour_end_ms,
                        "page_size": 1000,  # 1 hour = 720 records, safety margin
                    },
                )

                assert isinstance(response, dict)
                raw_records = response["results"]

                if raw_records:
                    # Aggregate this hour's records
                    hour_points = self._aggregate_to_hourly(raw_records)

                    if hour_points:
                        all_points.extend(hour_points)

                        logger.debug(
                            f"Fetched from API for {self.EXCHANGE_ID}/{symbol} "
                            f"hour {hour_end} ({len(raw_records)} records)"
                        )

        logger.debug(
            f"Fetched {len(all_points)} hourly points for {self.EXCHANGE_ID}/{symbol} "
            f"after {after_timestamp}"
        )

        return all_points

    def _aggregate_to_hourly(self, raw_records: list[dict]) -> list[FundingPoint]:
        """Aggregate raw 5-second records to hourly averages.

        Paradex API returns funding rate updates every ~5 seconds.
        Each record contains a raw 8-hour cumulative rate.
        We need to:
        1. Group records by hour
        2. Average all records in each hour
        3. Divide by 8 to get hourly rate

        Args:
            raw_records: List of raw API records with created_at and funding_rate

        Returns:
            List of hourly FundingPoint objects
        """
        # Group by hour
        hourly_groups: dict[int, list[float]] = {}

        for record in raw_records:
            created_at_ms = record["created_at"]
            rate = float(record["funding_rate"])

            # Find hour boundary (end of hour)
            hour_end_dt = start_of_hour(from_unix_milliseconds(created_at_ms)) + timedelta(hours=1)
            hour_end_ms = to_unix_milliseconds(hour_end_dt)

            if hour_end_ms not in hourly_groups:
                hourly_groups[hour_end_ms] = []
            hourly_groups[hour_end_ms].append(rate)

        # Calculate hourly averages
        points = []
        for hour_end_ms in sorted(hourly_groups.keys()):
            rates = hourly_groups[hour_end_ms]
            avg_rate = sum(rates) / len(rates)
            hourly_rate = avg_rate / 8  # Convert 8-hour period to hourly

            hour_end_dt = from_unix_milliseconds(hour_end_ms)
            points.append(FundingPoint(rate=hourly_rate, timestamp=hour_end_dt))

        return points

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        """Fetch funding history for contract within time window.

        Note: This method is not used for Paradex. We override fetch_history_before
        and fetch_history_after with custom logic. Always use those methods instead.
        """
        raise NotImplementedError(
            f"{self.EXCHANGE_ID}: _fetch_history() not supported. "
            f"Use fetch_history_before() or fetch_history_after() instead."
        )

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        """Fetch current funding rate for single contract.

        Stores the rate in live cache for fetch_after optimization.
        Cache entries are automatically removed when used via pop() in fetch_history_after.

        Note: Paradex doesn't have a dedicated "current rate" endpoint.
        We fetch the most recent historical record (page_size=1).
        """
        symbol = self._format_symbol(contract)
        contract_id = str(contract.id)

        response = await self._api_get(
            f"{self.API_ENDPOINT}/funding/data",
            params={
                "market": symbol,
                "page_size": 1,  # Most recent record only
            },
        )

        assert isinstance(response, dict)
        data = response["results"]

        if not data:
            raise ValueError(f"No funding rate data for {symbol}")

        record = data[0]
        raw_rate = float(record["funding_rate"])

        # Store in live cache for fetch_after optimization
        now = utc_now()
        hour_start = start_of_hour(now)
        hour_start_ms = to_unix_milliseconds(hour_start)

        if contract_id not in self._live_cache:
            self._live_cache[contract_id] = {}
        if hour_start_ms not in self._live_cache[contract_id]:
            self._live_cache[contract_id][hour_start_ms] = []

        self._live_cache[contract_id][hour_start_ms].append(raw_rate)

        # Divide by 8 for hourly rate
        hourly_rate = raw_rate / 8

        self.logger_live.debug(
            f"Fetched live rate for {symbol}: {hourly_rate:.8f} "
            f"(cached, hour bucket now has "
            f"{len(self._live_cache[contract_id][hour_start_ms])} records)"
        )

        return FundingPoint(rate=hourly_rate, timestamp=now)

    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        """Fetch unsettled rates for given contracts.

        Individual API pattern (no batch endpoint).
        Stores rates in live cache for fetch_after optimization.
        """
        return await self._fetch_live_parallel(contracts)
