"""Base exchange adapter using ABC."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint


class BaseExchange(ABC):
    """Base class for exchange adapters.

    Subclasses must implement all abstract methods.
    Prefer batch API if available; otherwise use fetch_live_parallel().
    """

    EXCHANGE_ID: str
    _FETCH_STEP: int

    """Fetch step size in hours (or records if exchange limits by records, not time).

    Calculated using MINIMUM funding interval to avoid exceeding API limits.
    Document per-exchange reasoning in class docstring.
    """

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

        Batch API exchanges should override this method.
        Individual API exchanges should implement _fetch_live_single()
        and use fetch_live_parallel() from utils.py.
        """
        ...

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        """Fetch single contract rate - override for individual API exchanges.

        Only implement this if exchange lacks batch API.
        Use fetch_live_parallel() for parallel execution.
        """
        raise NotImplementedError(
            f"{self.EXCHANGE_ID}: _fetch_live_single() not implemented. "
            "Override fetch_live() instead."
        )
