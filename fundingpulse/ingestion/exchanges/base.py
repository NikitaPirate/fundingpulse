"""Live-only exchange adapter base for ingestion workers."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from httpx import HTTPError

from fundingpulse.infrastructure import http_client
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract


class BaseLiveExchange(ABC):
    """Base class for live ingestion exchange adapters."""

    EXCHANGE_ID: str

    def __init__(self, request_limiter: asyncio.Semaphore | None = None) -> None:
        self._request_limiter = request_limiter

    async def _api_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> http_client.JsonValue:
        call = http_client.get if method == "GET" else http_client.post
        if self._request_limiter:
            async with self._request_limiter:
                return await call(url, **kwargs)
        return await call(url, **kwargs)

    async def _api_get(self, url: str, **kwargs: Any) -> http_client.JsonValue:
        return await self._api_request("GET", url, **kwargs)

    async def _api_post(self, url: str, **kwargs: Any) -> http_client.JsonValue:
        return await self._api_request("POST", url, **kwargs)

    @property
    def logger_live(self) -> logging.Logger:
        return logging.getLogger(f"fundingpulse.ingestion.exchanges.{self.EXCHANGE_ID}.live")

    @abstractmethod
    def _format_symbol(self, contract: Contract) -> str:
        """Format exchange-specific live symbol from a contract row."""
        ...

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        """Fetch unsettled rates for given contracts."""
        symbol_to_contract_id = {
            self._format_symbol(contract): contract.id for contract in contracts
        }
        all_rates = await self._fetch_live_batch()
        return {
            symbol_to_contract_id[symbol]: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract_id
        }

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        """Fetch all live rates in one API call for batch exchanges."""
        raise NotImplementedError(
            f"{self.EXCHANGE_ID}: _fetch_live_batch() is not implemented. "
            "Override fetch_live() for non-batch exchanges."
        )

    async def _fetch_live_single(self, contract: Contract) -> FundingPoint:
        """Fetch one live rate for per-contract exchanges."""
        raise NotImplementedError

    async def _fetch_live_parallel(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        """Fetch live rates through parallel per-contract requests."""

        async def _fetch_one(contract: Contract) -> FundingPoint | None:
            try:
                return await self._fetch_live_single(contract)
            except HTTPError as exc:
                self.logger_live.warning(
                    "Failed to fetch live rate for %s: %s",
                    contract.asset_name,
                    exc,
                )
                return None
            except ValueError as exc:
                self.logger_live.warning(
                    "Invalid funding rate data for %s: %s",
                    contract.asset_name,
                    exc,
                )
                return None

        results = await asyncio.gather(*(_fetch_one(contract) for contract in contracts))
        return {
            contract.id: result
            for contract, result in zip(contracts, results, strict=True)
            if result is not None
        }
