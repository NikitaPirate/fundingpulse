"""Common utilities for exchange adapters."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from httpx import HTTPError

from fundingpulse.models.contract import Contract
from fundingpulse.tracker.exchanges.dto import FundingPoint

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


def to_ms_timestamp(dt: datetime | None) -> int:
    """Convert datetime to milliseconds since Unix epoch; None returns 0."""
    return int(dt.timestamp() * 1000) if dt else 0


def to_sec_timestamp(dt: datetime | None) -> int:
    """Convert datetime to seconds since Unix epoch; None returns 0."""
    return int(dt.timestamp()) if dt else 0


def from_ms_timestamp(ms: int) -> datetime:
    """Parse milliseconds timestamp to datetime."""
    return datetime.fromtimestamp(ms / 1000.0)


def from_sec_timestamp(sec: int) -> datetime:
    """Parse seconds timestamp to datetime."""
    return datetime.fromtimestamp(sec)


async def fetch_live_parallel(
    exchange: BaseExchange,
    contracts: list[Contract],
) -> dict[Contract, FundingPoint]:
    """Fetch live rates using parallel individual API calls.

    Executes requests concurrently with semaphore-controlled rate limiting.
    Returns dict of successfully fetched contracts; logs and filters failures.
    """

    async def fetch_one(contract: Contract) -> FundingPoint | None:
        async with semaphore:
            try:
                return await exchange._fetch_live_single(contract)
            except HTTPError as e:
                exchange.logger_live.warning(
                    f"Failed to fetch live rate for {contract.asset.name}: {e}"
                )
                return None
            except ValueError as e:
                exchange.logger_live.warning(
                    f"Invalid funding rate data for {contract.asset.name}: {e}"
                )
                return None

    semaphore = asyncio.Semaphore(10)
    tasks = [fetch_one(contract) for contract in contracts]
    results = await asyncio.gather(*tasks)

    return {
        contract: result
        for contract, result in zip(contracts, results, strict=True)
        if result is not None
    }
