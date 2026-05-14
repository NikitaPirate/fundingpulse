"""Live ingestion exchange adapters."""

import asyncio
from collections.abc import Iterable

from fundingpulse.ingestion.exchanges.aster import AsterLiveExchange
from fundingpulse.ingestion.exchanges.backpack import BackpackLiveExchange
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.binance_coinm import BinanceCoinmLiveExchange
from fundingpulse.ingestion.exchanges.binance_usdm import BinanceUsdmLiveExchange
from fundingpulse.ingestion.exchanges.bybit import BybitLiveExchange
from fundingpulse.ingestion.exchanges.derive import DeriveLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.ingestion.exchanges.dydx import DydxLiveExchange
from fundingpulse.ingestion.exchanges.extended import ExtendedLiveExchange
from fundingpulse.ingestion.exchanges.hyperliquid import HyperliquidLiveExchange
from fundingpulse.ingestion.exchanges.hyperliquid_xyz import HyperliquidXyzLiveExchange
from fundingpulse.ingestion.exchanges.kucoin import KucoinLiveExchange
from fundingpulse.ingestion.exchanges.lighter import LighterLiveExchange
from fundingpulse.ingestion.exchanges.okx import OkxLiveExchange
from fundingpulse.ingestion.exchanges.pacifica import PacificaLiveExchange
from fundingpulse.ingestion.exchanges.paradex import ParadexLiveExchange

_LIVE_ADAPTERS: dict[str, type[BaseLiveExchange]] = {
    "aster": AsterLiveExchange,
    "backpack": BackpackLiveExchange,
    "binance_usd-m": BinanceUsdmLiveExchange,
    "binance_coin-m": BinanceCoinmLiveExchange,
    "bybit": BybitLiveExchange,
    "derive": DeriveLiveExchange,
    "dydx": DydxLiveExchange,
    "extended": ExtendedLiveExchange,
    "hyperliquid": HyperliquidLiveExchange,
    "hyperliquid-xyz": HyperliquidXyzLiveExchange,
    "kucoin": KucoinLiveExchange,
    "lighter": LighterLiveExchange,
    "okx": OkxLiveExchange,
    "pacifica": PacificaLiveExchange,
    "paradex": ParadexLiveExchange,
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
    "AsterLiveExchange",
    "BackpackLiveExchange",
    "BaseLiveExchange",
    "BinanceCoinmLiveExchange",
    "BinanceUsdmLiveExchange",
    "BybitLiveExchange",
    "DeriveLiveExchange",
    "DydxLiveExchange",
    "ExtendedLiveExchange",
    "FundingPoint",
    "HyperliquidLiveExchange",
    "HyperliquidXyzLiveExchange",
    "KucoinLiveExchange",
    "LighterLiveExchange",
    "OkxLiveExchange",
    "PacificaLiveExchange",
    "ParadexLiveExchange",
    "build_live_exchange_adapters",
]
