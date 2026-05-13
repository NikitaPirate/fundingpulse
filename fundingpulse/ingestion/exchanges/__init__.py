"""Live ingestion exchange adapters."""

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.bybit import BybitLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.ingestion.exchanges.okx import OkxLiveExchange

LIVE_EXCHANGES: dict[str, type[BaseLiveExchange]] = {
    "bybit": BybitLiveExchange,
    "okx": OkxLiveExchange,
}

__all__ = [
    "LIVE_EXCHANGES",
    "BaseLiveExchange",
    "BybitLiveExchange",
    "FundingPoint",
    "OkxLiveExchange",
]
