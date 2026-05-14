"""Hyperliquid live funding adapter."""

from __future__ import annotations

from typing import Any

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class HyperliquidLiveExchange(BaseLiveExchange):
    """Hyperliquid live adapter using the meta-and-contexts endpoint."""

    EXCHANGE_ID = "hyperliquid"
    API_ENDPOINT = "https://api.hyperliquid.xyz/info"
    _DEX: str | None = None

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset_name

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        json_payload: dict[str, Any] = {"type": "metaAndAssetCtxs"}
        if self._DEX:
            json_payload["dex"] = self._DEX

        response: Any = await self._api_post(
            self.API_ENDPOINT,
            json=json_payload,
            headers={"Content-Type": "application/json"},
        )
        assert isinstance(response, list)

        meta_data = response[0]["universe"]
        asset_contexts = response[1]
        asset_names = {
            index: asset["name"].split(":")[-1] for index, asset in enumerate(meta_data)
        }

        now = utc_now()
        rates: dict[str, FundingPoint] = {}
        for index, context in enumerate(asset_contexts):
            if "funding" in context:
                rates[asset_names[index]] = FundingPoint(
                    rate=float(context["funding"]),
                    timestamp=now,
                )
        return rates
