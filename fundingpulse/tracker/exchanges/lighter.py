"""Lighter exchange adapter.

Lighter uses 1-hour funding interval. API limit is 500 records per request.
_FETCH_STEP = 498 hours (500 - 2 safety buffer).
"""

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import websockets

from fundingpulse.models.contract import Contract
from fundingpulse.time import from_unix_seconds, utc_now
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint

logger = logging.getLogger(__name__)


class LighterExchange(BaseExchange):
    """Lighter exchange adapter."""

    EXCHANGE_ID = "lighter"
    API_ENDPOINT = "https://mainnet.zklighter.elliot.ai/api/v1"
    WS_ENDPOINT = "wss://mainnet.zklighter.elliot.ai/stream"

    # 500 records max, 1-hour interval -> 498 hours (500 - 2 safety buffer)
    _FETCH_STEP = 498

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._asset_to_id: dict[str, int] = {}

    def _format_symbol(self, contract: Contract) -> str:
        return str(self._asset_to_id[contract.asset_name])

    async def _fetch_order_books(self) -> list[dict[str, Any]]:
        response = await self._api_get(f"{self.API_ENDPOINT}/orderBooks")

        assert isinstance(response, dict)

        return [
            market
            for market in response.get("order_books", [])
            if market.get("market_type") == "perp"
        ]

    async def _refresh_asset_to_id(self) -> None:
        markets = await self._fetch_order_books()
        self._asset_to_id = {market["symbol"]: int(market["market_id"]) for market in markets}

    async def _ensure_asset_to_id(self, contracts: list[Contract]) -> None:
        if any(contract.asset_name not in self._asset_to_id for contract in contracts):
            await self._refresh_asset_to_id()

    def _has_unknown_market_ids(self, rates: dict[str, FundingPoint]) -> bool:
        known_market_ids = {str(market_id) for market_id in self._asset_to_id.values()}
        return any(market_id not in known_market_ids for market_id in rates)

    async def get_contracts(self) -> list[ExchangeContractListing]:
        markets = await self._fetch_order_books()
        contracts = []
        asset_to_id: dict[str, int] = {}

        for market in markets:
            asset_name = market["symbol"]
            asset_to_id[asset_name] = int(market["market_id"])
            contracts.append(
                ExchangeContractListing(
                    asset_name=asset_name,
                    quote_name="USD",
                    funding_interval=1,
                    section_name=self.EXCHANGE_ID,
                )
            )

        self._asset_to_id = asset_to_id
        return contracts

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        await self._ensure_asset_to_id([contract])
        symbol = self._format_symbol(contract)

        response = await self._api_get(
            f"{self.API_ENDPOINT}/fundings",
            params={
                "market_id": int(symbol),
                "resolution": "1h",
                "start_timestamp": start_ms // 1000,
                "end_timestamp": end_ms // 1000,
                "count_back": 500,
            },
        )

        assert isinstance(response, dict)

        points = []
        raw_records = response.get("fundings", [])

        for raw_record in raw_records:
            rate = float(raw_record["rate"]) / 100
            if raw_record["direction"] == "short":
                rate = -rate
            timestamp = from_unix_seconds(raw_record["timestamp"])
            points.append(FundingPoint(rate=rate, timestamp=timestamp))

        return points

    async def _fetch_live_batch(self) -> dict[str, FundingPoint]:
        async with asyncio.timeout(30), websockets.connect(self.WS_ENDPOINT) as ws:
            await ws.send(json.dumps({"type": "subscribe", "channel": "market_stats/all"}))
            await ws.recv()  # skip "connected" ack
            data = json.loads(await ws.recv())

        now = utc_now()
        return {
            market_id: FundingPoint(
                rate=float(payload["current_funding_rate"]) / 100, timestamp=now
            )
            for market_id, payload in data.get("market_stats", {}).items()
            if payload.get("current_funding_rate") is not None
        }

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        all_rates = await self._fetch_live_batch()
        if self._has_unknown_market_ids(all_rates):
            await self._refresh_asset_to_id()
        else:
            await self._ensure_asset_to_id(contracts)

        symbol_to_contract = {
            self._format_symbol(contract): contract
            for contract in contracts
            if contract.asset_name in self._asset_to_id
        }
        return {
            symbol_to_contract[symbol].id: rate
            for symbol, rate in all_rates.items()
            if symbol in symbol_to_contract
        }
