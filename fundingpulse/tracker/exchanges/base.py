"""Base exchange adapter using ABC."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from httpx import HTTPError

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint
from fundingpulse.tracker.infrastructure import http_client


class BaseExchange(ABC):
    """Base class for exchange adapters.

    Subclasses must implement all abstract methods.
    All HTTP requests go through _api_get/_api_post which enforce
    per-exchange rate limiting via semaphore.
    """

    EXCHANGE_ID: str
    _FETCH_STEP: int

    """Fetch step size in hours (or records if exchange limits by records, not time).

    Calculated using MINIMUM funding interval to avoid exceeding API limits.
    Document per-exchange reasoning in class docstring.
    """

    def __init__(self, semaphore: asyncio.Semaphore | None = None) -> None:
        self._semaphore = semaphore

    async def _api_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> http_client.JsonValue:
        """Rate-limited HTTP request. All adapter HTTP calls go through here."""
        call = http_client.get if method == "GET" else http_client.post
        if self._semaphore:
            async with self._semaphore:
                return await call(url, **kwargs)
        return await call(url, **kwargs)

    async def _api_get(self, url: str, **kwargs: Any) -> http_client.JsonValue:
        return await self._api_request("GET", url, **kwargs)

    async def _api_post(self, url: str, **kwargs: Any) -> http_client.JsonValue:
        return await self._api_request("POST", url, **kwargs)

    @property
    def logger(self) -> logging.Logger:
        """Exchange logger for use in coordinators.

        Enables per-exchange log control via LOGLEVEL=funding_tracker.exchanges.{EXCHANGE_ID}:LEVEL
        """
        return logging.getLogger(f"funding_tracker.exchanges.{self.EXCHANGE_ID}")

    @property
    def logger_live(self) -> logging.Logger:
        """Dedicated logger for live collection operations.

        Enables independent live log control via DEBUG_EXCHANGES_LIVE or per-exchange:
        LOGLEVEL=funding_tracker.exchanges.{EXCHANGE_ID}.live:LEVEL
        """
        return logging.getLogger(f"funding_tracker.exchanges.{self.EXCHANGE_ID}.live")

    def __init_subclass__(cls) -> None:
        """Validate subclass implements required methods."""
        super().__init_subclass__()

        if not hasattr(cls, "EXCHANGE_ID"):
            raise NotImplementedError(f"{cls.__name__}: missing EXCHANGE_ID class attribute")

    @abstractmethod
    def _format_symbol(self, contract: Contract) -> str:
        """Format exchange-specific symbol from Contract."""
        ...

    @abstractmethod
    async def get_contracts(self) -> list[ContractInfo]:
        """Fetch all perpetual contracts from exchange."""
        ...

    @abstractmethod
    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        """Fetch funding history for contract within time window.

        Returns points in chronological order.
        May contain duplicates - caller handles deduplication.
        """
        ...

    async def fetch_history_before(
        self, contract: Contract, before_timestamp: datetime | None
    ) -> list[FundingPoint]:
        """Fetch funding points before timestamp (backward sync).

        Default implementation works for most exchanges using _fetch_history().
        Override if exchange has different pagination/fetching/offset logic.
        """
        end_ms = int(
            (before_timestamp.timestamp() if before_timestamp else datetime.now().timestamp())
            * 1000
        )
        start_ms = end_ms - (self._FETCH_STEP * 3600 * 1000)
        return await self._fetch_history(contract, start_ms, end_ms)

    async def fetch_history_after(
        self, contract: Contract, after_timestamp: datetime
    ) -> list[FundingPoint]:
        """Fetch funding points after timestamp (forward sync).

        Default implementation works for most exchanges using _fetch_history().
        Override if exchange has different pagination/fetching/offset logic.
        """
        start_ms = int(after_timestamp.timestamp() * 1000)
        end_ms = int(datetime.now().timestamp() * 1000)
        return await self._fetch_history(contract, start_ms, end_ms)

    @abstractmethod
    async def fetch_live(self, contracts: list[Contract]) -> dict[Contract, FundingPoint]:
        """Fetch unsettled rates for given contracts.

        Batch exchanges override with a single API call.
        Individual API exchanges implement _fetch_live_single() and call
        self._fetch_live_parallel(contracts) here.
        """
        ...

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        """Fetch single contract rate — override for individual API exchanges.

        Only implement this if exchange lacks batch API.
        Called from _fetch_live_parallel(); uses _api_get internally.
        """
        raise NotImplementedError(
            f"{self.EXCHANGE_ID}: _fetch_live_single() not implemented. "
            "Override fetch_live() instead."
        )

    async def _fetch_live_parallel(
        self, contracts: list[Contract]
    ) -> dict[Contract, FundingPoint]:
        """Fetch live rates via parallel per-contract requests.

        For exchanges without batch API. Calls _fetch_live_single() for each
        contract concurrently. Rate limiting is handled by _api_get inside
        each _fetch_live_single() call.
        """

        async def _fetch_one(contract: Contract) -> FundingPoint | None:
            try:
                return await self._fetch_live_single(contract)
            except HTTPError as e:
                self.logger_live.warning(
                    f"Failed to fetch live rate for {contract.asset.name}: {e}"
                )
                return None
            except ValueError as e:
                self.logger_live.warning(
                    f"Invalid funding rate data for {contract.asset.name}: {e}"
                )
                return None

        tasks = [_fetch_one(contract) for contract in contracts]
        results = await asyncio.gather(*tasks)

        return {
            contract: result
            for contract, result in zip(contracts, results, strict=True)
            if result is not None
        }
