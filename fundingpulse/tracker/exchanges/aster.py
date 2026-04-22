"""Aster exchange adapter.

Aster uses variable funding intervals (1, 4, or 8 hours) per symbol.
API does NOT provide funding_interval directly - must detect per symbol.
API limit is 1000 records per request.
_FETCH_STEP = 8000 hours (~333 days with 3 records/day for 8-hour interval symbols).

**Key Challenge:**
Each symbol has different funding interval (1, 4, or 8 hours).
Must detect interval by fetching last funding rate and comparing with nextFundingTime
from premiumIndex.

**API Characteristics:**
- Binance-style format: BTCUSDT (no dash)
- Batch premiumIndex API: returns all markets in one request
- Standard response: direct list/dict (no envelope)

**Fetching Strategy:**
- get_contracts: Detect funding interval per symbol via parallel API calls
- fetch_history: Standard time-based batching (8000 hours = 333 days)
- fetch_live: Batch API (all markets in one request)
"""

import asyncio
import logging

from fundingpulse.time import from_unix_milliseconds, utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint

logger = logging.getLogger(__name__)


class AsterExchange(BaseExchange):
    """Aster exchange adapter with per-symbol funding interval detection."""

    EXCHANGE_ID = "aster"
    API_ENDPOINT = "https://fapi.asterdex.com/fapi"

    # ~333 days (1000 records / 3 records per day for 8-hour interval)
    _FETCH_STEP = 8000

    def _format_symbol(self, contract: TrackedContract) -> str:
        return f"{contract.asset_name}{contract.quote_name}"

    async def get_contracts(self) -> list[ExchangeContractListing]:
        """Fetch all perpetual contracts with detected funding intervals.

        Funding interval detection requires:
        1. Fetch exchangeInfo for perpetual contract list
        2. Fetch premiumIndex for nextFundingTime data
        3. For EACH symbol: fetch last funding rate → calculate interval
        4. Use parallel execution with semaphore control
        """
        logger.debug(f"Fetching contracts from {self.EXCHANGE_ID}")

        # Fetch exchangeInfo and premiumIndex in parallel
        exchange_response, premium_response = await asyncio.gather(
            self._api_get(f"{self.API_ENDPOINT}/v1/exchangeInfo"),
            self._api_get(f"{self.API_ENDPOINT}/v1/premiumIndex"),
        )

        exchange_data = exchange_response
        assert isinstance(exchange_data, dict), "exchangeInfo must return dict"

        premium_data = premium_response
        assert isinstance(premium_data, list), "premiumIndex must return list"

        # Build premium index lookup
        premium_lookup = {item["symbol"]: item for item in premium_data}

        # Build symbol list from perpetual contracts
        symbols_to_process = []
        symbol_to_asset_quote = {}

        for symbol_info in exchange_data.get("symbols", []):
            if (
                symbol_info.get("contractType") == "PERPETUAL"
                and symbol_info.get("status") == "TRADING"
            ):
                base_asset = symbol_info.get("baseAsset", "")
                quote_asset = symbol_info.get("quoteAsset", "")

                if not base_asset or not quote_asset:
                    continue

                symbol = base_asset + quote_asset

                if symbol not in premium_lookup:
                    logger.warning(f"Symbol {symbol} not found in premiumIndex, skipping")
                    continue

                symbols_to_process.append(symbol)
                symbol_to_asset_quote[symbol] = (base_asset, quote_asset)

        # Detect funding intervals for all symbols in parallel
        tasks = [
            self._detect_funding_interval(symbol, premium_lookup[symbol])
            for symbol in symbols_to_process
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        contracts = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Task failed with exception: {result}")
                continue

            if result is None:
                continue

            if not isinstance(result, tuple) or len(result) != 2:
                logger.warning(f"Unexpected result type: {type(result)}")
                continue

            symbol, funding_interval = result

            if symbol not in symbol_to_asset_quote:
                logger.warning(f"Symbol {symbol} not found in mapping")
                continue

            base_asset, quote_asset = symbol_to_asset_quote[symbol]

            contracts.append(
                ExchangeContractListing(
                    asset_name=base_asset,
                    quote_name=quote_asset,
                    funding_interval=funding_interval,
                    section_name=self.EXCHANGE_ID,
                )
            )

        logger.debug(
            f"Fetched {len(contracts)} contracts from {self.EXCHANGE_ID} "
            f"(with detected funding intervals)"
        )
        return contracts

    async def _detect_funding_interval(
        self, symbol: str, premium_item: dict
    ) -> tuple[str, int] | None:
        """Detect funding interval for a symbol by comparing last and next funding times.

        Fetches the last funding rate record and compares its timestamp with
        nextFundingTime from premiumIndex to calculate the funding interval.
        """
        try:
            response = await self._api_get(
                f"{self.API_ENDPOINT}/v1/fundingRate",
                params={"symbol": symbol, "limit": 1},
            )

            last_funding_data = response
            assert isinstance(last_funding_data, list), "fundingRate must return list"

            if not last_funding_data:
                logger.warning(f"No historical funding data found for {symbol}")
                return None

            last_funding_time = last_funding_data[0]["fundingTime"]
            next_funding_time = premium_item["nextFundingTime"]

            # Calculate interval in hours
            interval_ms = next_funding_time - last_funding_time
            interval_hours = interval_ms / 1000 / 3600

            if interval_hours <= 0:
                logger.warning(f"Invalid funding interval {interval_hours}h for {symbol}")
                return None

            funding_interval = int(max(1, round(interval_hours)))
            return symbol, funding_interval

        except Exception as e:
            logger.warning(f"Failed to get funding interval for {symbol}: {e}")
            return None

    async def _fetch_history(
        self, contract: TrackedContract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response = await self._api_get(
            f"{self.API_ENDPOINT}/v1/fundingRate",
            params={
                "symbol": symbol,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            },
        )

        raw_records = response
        assert isinstance(raw_records, list), "fundingRate history must return list"

        points = []
        if raw_records:
            for record in raw_records:
                rate = float(record["fundingRate"])
                timestamp = from_unix_milliseconds(record["fundingTime"])
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        response = await self._api_get(f"{self.API_ENDPOINT}/v1/premiumIndex")

        markets = response
        assert isinstance(markets, list), "premiumIndex must return list"
        now = utc_now()

        rates = {}
        for market in markets:
            symbol = market["symbol"]
            rate = float(market["lastFundingRate"])
            rates[symbol] = FundingPoint(rate=rate, timestamp=now)

        return rates
