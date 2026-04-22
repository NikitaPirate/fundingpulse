"""Hyperliquid exchange adapter.

HyperLiquid uses 1-hour funding interval. API limit is 500 records per request.
_FETCH_STEP = 498 hours (500 - 2 safety buffer).
"""

import logging

from fundingpulse.time import from_unix_milliseconds, utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

logger = logging.getLogger(__name__)


class HyperliquidExchange(BaseExchange):
    """Hyperliquid exchange adapter."""

    EXCHANGE_ID = "hyperliquid"
    API_ENDPOINT = "https://api.hyperliquid.xyz/info"

    # 500 records max, 1-hour interval -> 498 hours (500 - 2 safety buffer)
    _FETCH_STEP = 498

    # Optional DEX parameter for sub-dex variants (e.g., "xyz")
    _DEX: str | None = None

    def _format_symbol(self, contract: TrackedContract) -> str:
        return contract.asset_name

    async def get_contracts(self) -> list[ContractInfo]:
        json_payload = {"type": "meta"}
        if self._DEX:
            json_payload["dex"] = self._DEX

        response = await self._api_post(
            self.API_ENDPOINT,
            json=json_payload,
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, dict)

        contracts = []
        for listing in response["universe"]:
            contracts.append(
                ContractInfo(
                    asset_name=listing["name"],
                    quote="USD",
                    funding_interval=1,
                    section_name=self.EXCHANGE_ID,
                )
            )

        return contracts

    async def _fetch_history(
        self, contract: TrackedContract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        symbol = self._format_symbol(contract)

        response = await self._api_post(
            self.API_ENDPOINT,
            json={
                "type": "fundingHistory",
                "coin": symbol,
                "startTime": start_ms,
                "endTime": end_ms,
            },
            headers={"Content-Type": "application/json"},
        )

        points = []
        if response:
            assert isinstance(response, list)
            for raw_record in response:
                rate = float(raw_record["fundingRate"])
                timestamp = from_unix_milliseconds(raw_record["time"])
                points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        json_payload = {"type": "metaAndAssetCtxs"}
        if self._DEX:
            json_payload["dex"] = self._DEX

        response = await self._api_post(
            self.API_ENDPOINT,
            json=json_payload,
            headers={"Content-Type": "application/json"},
        )

        assert isinstance(response, list)
        meta_data = response[0]["universe"]
        asset_contexts = response[1]

        # Handle both prefixed symbols (xyz:GOLD) and non-prefixed (BTC)
        asset_names = {}
        for i, asset in enumerate(meta_data):
            full_name = asset["name"]
            # Extract base name after colon if present
            base_name = full_name.split(":")[-1]
            asset_names[i] = base_name

        now = utc_now()
        rates = {}
        for idx, ctx in enumerate(asset_contexts):
            if "funding" in ctx:
                asset_name = asset_names[idx]
                rates[asset_name] = FundingPoint(
                    rate=float(ctx["funding"]),
                    timestamp=now,
                )

        return rates
