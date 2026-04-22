"""Hyperliquid XYZ exchange adapter.

Sub-dex with stocks, metals, and forex. Uses symbol mapping
for standardization (GOLD -> XAU, SILVER -> XAG).
"""

from uuid import UUID

from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint
from fundingpulse.tracker.exchanges.hyperliquid import HyperliquidExchange

# Symbol mapping for standardization (API symbol -> Database symbol)
_SYMBOL_MAP: dict[str, str] = {
    "GOLD": "XAU",
    "SILVER": "XAG",
    "PLATINUM": "XPT",
    "COPPER": "XCU",
    "ALUMINIUM": "XAL",
}

# Reverse mapping: database symbol -> API symbol
_REVERSE_MAP: dict[str, str] = {v: k for k, v in _SYMBOL_MAP.items()}


class HyperliquidXyzExchange(HyperliquidExchange):
    """Hyperliquid XYZ sub-dex exchange adapter."""

    EXCHANGE_ID = "hyperliquid-xyz"
    _DEX = "xyz"

    def _format_symbol(self, contract: TrackedContract) -> str:
        """Convert database symbol to API format (XAU -> xyz:GOLD)."""
        db_symbol = contract.asset_name  # "XAU"
        xyz_symbol = _REVERSE_MAP.get(db_symbol, db_symbol)  # "GOLD" or fallback
        return f"xyz:{xyz_symbol}"

    async def get_contracts(self) -> list[ExchangeContractListing]:
        # Call parent to get raw data with dex=xyz
        raw_contracts = await super().get_contracts()

        # Apply symbol mapping (GOLD -> XAU)
        mapped_contracts = []
        for contract in raw_contracts:
            asset_part = contract.asset_name.split(":")[-1]  # Extract "GOLD" from "xyz:GOLD"
            mapped_name = _SYMBOL_MAP.get(asset_part, asset_part)

            mapped_contracts.append(
                ExchangeContractListing(
                    asset_name=mapped_name,
                    quote_name=contract.quote_name,
                    funding_interval=contract.funding_interval,
                    section_name=self.EXCHANGE_ID,
                )
            )

        return mapped_contracts

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        # Call parent to get rates with dex=xyz
        raw_rates = await super()._fetch_live_batch()

        # Map keys from GOLD/SILVER to XAU/XAG to match get_contracts()
        mapped_rates = {}
        for symbol, rate_point in raw_rates.items():
            mapped_name = _SYMBOL_MAP.get(symbol, symbol)
            mapped_rates[mapped_name] = rate_point

        return mapped_rates

    async def fetch_live(self, contracts: list[TrackedContract]) -> dict[UUID, FundingPoint]:
        # Use database symbol (XAU) as key, not API format (xyz:GOLD)
        symbol_to_contract = {c.asset_name: c for c in contracts}
        all_rates = await self._fetch_live_batch()

        return {
            symbol_to_contract[symbol].id: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract
        }
