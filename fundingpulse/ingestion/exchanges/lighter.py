"""Lighter live funding adapter."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import websockets

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class LighterLiveExchange(BaseLiveExchange):
    """Lighter live adapter using the market stats WebSocket stream."""

    EXCHANGE_ID = "lighter"
    API_ENDPOINT = "https://mainnet.zklighter.elliot.ai/api/v1"
    WS_ENDPOINT = "wss://mainnet.zklighter.elliot.ai/stream"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._asset_to_id: dict[str, int] = {}
        self._asset_to_id_lock = asyncio.Lock()

    def _format_symbol(self, contract: Contract) -> str:
        return str(self._asset_to_id[contract.asset_name])

    async def _refresh_asset_to_id(self) -> None:
        async with self._asset_to_id_lock:
            response = await self._api_get(f"{self.API_ENDPOINT}/orderBooks")

            assert isinstance(response, dict)

            self._asset_to_id = {
                market["symbol"]: int(market["market_id"])
                for market in response.get("order_books", [])
                if market.get("market_type") == "perp"
            }

    def _has_unknown_market_ids(self, rates: dict[str, FundingPoint]) -> bool:
        known_market_ids = {str(market_id) for market_id in self._asset_to_id.values()}
        return any(market_id not in known_market_ids for market_id in rates)

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        all_rates = await self._fetch_live_batch()
        if self._has_unknown_market_ids(all_rates):
            await self._refresh_asset_to_id()

        symbol_to_contract_id = {
            self._format_symbol(contract): contract.id
            for contract in contracts
            if contract.asset_name in self._asset_to_id
        }
        return {
            symbol_to_contract_id[symbol]: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract_id
        }

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        async with asyncio.timeout(30), websockets.connect(self.WS_ENDPOINT) as ws:
            await ws.send(json.dumps({"type": "subscribe", "channel": "market_stats/all"}))
            await ws.recv()
            data = json.loads(await ws.recv())

        now = utc_now()
        return {
            market_id: FundingPoint(
                rate=float(payload["current_funding_rate"]) / 100,
                timestamp=now,
            )
            for market_id, payload in data.get("market_stats", {}).items()
            if payload.get("current_funding_rate") is not None
        }
