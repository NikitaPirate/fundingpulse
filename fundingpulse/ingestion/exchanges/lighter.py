"""Lighter live funding adapter."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_now


class LighterLiveExchange(BaseLiveExchange):
    """Lighter live adapter using the market stats WebSocket stream."""

    EXCHANGE_ID = "lighter"
    WS_ENDPOINT = "wss://mainnet.zklighter.elliot.ai/stream"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._asset_to_id: dict[str, int] = {}

    def _format_symbol(self, contract: Contract) -> str:
        return str(self._asset_to_id[contract.asset_name])

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
