"""Live ingestion exchange adapters."""

import asyncio
from collections.abc import Iterable

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.bybit import BybitLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.ingestion.exchanges.okx import OkxLiveExchange

_LIVE_ADAPTERS: dict[str, type[BaseLiveExchange]] = {
    "bybit": BybitLiveExchange,
    "okx": OkxLiveExchange,
}


def build_live_exchange_adapters(
    exchanges: Iterable[str],
    *,
    request_limiter: asyncio.Semaphore | None = None,
) -> dict[str, BaseLiveExchange]:
    """Build adapters currently implemented for the requested exchange IDs."""
    return {
        exchange: adapter_cls(request_limiter=request_limiter)
        for exchange in exchanges
        if (adapter_cls := _LIVE_ADAPTERS.get(exchange)) is not None
    }


__all__ = [
    "BaseLiveExchange",
    "BybitLiveExchange",
    "FundingPoint",
    "OkxLiveExchange",
    "build_live_exchange_adapters",
]
