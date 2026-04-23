"""Lighter exchange adapter.

Lighter uses 1-hour funding interval. API limit is 500 records per request.
_FETCH_STEP = 498 hours (500 - 2 safety buffer).
"""

import asyncio
import json
import logging

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

    async def get_contracts(self) -> list[ExchangeContractListing]:
        response = await self._api_get(f"{self.API_ENDPOINT}/orderBooks")

        assert isinstance(response, dict)

        contracts = []
        asset_to_id = {}

        for market in response.get("order_books", []):
            if market.get("market_type") != "perp":
                continue
            asset_name = market["symbol"]
            asset_to_id[asset_name] = market["market_id"]
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
