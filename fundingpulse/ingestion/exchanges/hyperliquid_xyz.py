"""Hyperliquid XYZ live funding adapter."""

from __future__ import annotations

from uuid import UUID

from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.ingestion.exchanges.hyperliquid import HyperliquidLiveExchange
from fundingpulse.models.contract import Contract

_SYMBOL_MAP: dict[str, str] = {
    "GOLD": "XAU",
    "SILVER": "XAG",
    "PLATINUM": "XPT",
    "COPPER": "XCU",
    "ALUMINIUM": "XAL",
}
_REVERSE_MAP: dict[str, str] = {value: key for key, value in _SYMBOL_MAP.items()}


class HyperliquidXyzLiveExchange(HyperliquidLiveExchange):
    """Hyperliquid XYZ live adapter with database/API symbol mapping."""

    EXCHANGE_ID = "hyperliquid-xyz"
    _DEX = "xyz"

    def _format_symbol(self, contract: Contract) -> str:
        xyz_symbol = _REVERSE_MAP.get(contract.asset_name, contract.asset_name)
        return f"xyz:{xyz_symbol}"

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        raw_rates = await super()._fetch_live_batch()
        return {
            _SYMBOL_MAP.get(symbol, symbol): rate_point for symbol, rate_point in raw_rates.items()
        }

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        symbol_to_contract = {contract.asset_name: contract for contract in contracts}
        all_rates = await self._fetch_live_batch()
        return {
            symbol_to_contract[symbol].id: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract
        }
