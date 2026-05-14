"""Parametrized live parsing tests for ingestion exchange adapters."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from fundingpulse.infrastructure import http_client
from fundingpulse.ingestion.exchanges import build_live_exchange_adapters
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.models.contract import Contract
from fundingpulse.time import UtcDateTime

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ADAPTER_IDS = sorted(path.stem for path in FIXTURES_DIR.glob("*.json"))

MockHttp = Callable[..., tuple["HttpCallRecorder", "HttpCallRecorder"]]


class HttpCallRecorder:
    """Replays HTTP responses in call order. Raises on unexpected extra calls."""

    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self._index = 0

    @property
    def call_count(self) -> int:
        return self._index

    async def __call__(self, url: str, **kwargs: object) -> object:
        del url, kwargs
        if self._index >= len(self._responses):
            raise RuntimeError(f"HTTP mock exhausted after {len(self._responses)} call(s)")
        response = self._responses[self._index]
        self._index += 1
        return response


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> MockHttp:
    def _setup(
        get_responses: list[object] | None = None,
        post_responses: list[object] | None = None,
    ) -> tuple[HttpCallRecorder, HttpCallRecorder]:
        get_recorder = HttpCallRecorder(get_responses or [])
        post_recorder = HttpCallRecorder(post_responses or [])
        monkeypatch.setattr(http_client, "get", get_recorder)
        monkeypatch.setattr(http_client, "post", post_recorder)
        return get_recorder, post_recorder

    return _setup


def load_fixture(exchange_id: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / f"{exchange_id}.json").read_text())


def build_contract(defn: dict[str, Any]) -> Contract:
    return Contract(
        id=uuid4(),
        asset_name=defn["asset_name"],
        quote_name=defn["quote_name"],
        section_name=defn["section_name"],
        funding_interval=defn["funding_interval"],
    )


def make_adapter(exchange_id: str) -> BaseLiveExchange:
    return build_live_exchange_adapters([exchange_id])[exchange_id]


def assert_aware_utc_timestamp(value: UtcDateTime) -> None:
    assert value.tzinfo is not None
    offset = value.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


@pytest.mark.parametrize("exchange_id", ADAPTER_IDS)
@pytest.mark.asyncio
async def test_fetch_live_returns_contract_funding_points(
    exchange_id: str,
    mock_http: MockHttp,
) -> None:
    """fetch_live returns contract-keyed FundingPoint values."""
    fixture = load_fixture(exchange_id)
    scenario = fixture["fetch_live"]
    mock_http(scenario.get("http_get", []), scenario.get("http_post", []))
    contract = build_contract(scenario["contract"])
    adapter = make_adapter(exchange_id)

    result = await adapter.fetch_live([contract])

    assert len(result) >= scenario["expected_count_gte"]
    assert set(result) == {contract.id}
    assert all(isinstance(point, FundingPoint) for point in result.values())
    assert all(isinstance(point.rate, float) for point in result.values())
    for point in result.values():
        assert_aware_utc_timestamp(point.timestamp)


@pytest.mark.asyncio
async def test_built_live_adapter_uses_request_limiter(
    mock_http: MockHttp,
) -> None:
    """Built adapters route HTTP calls through the supplied limiter."""
    fixture = load_fixture("bybit")
    scenario = fixture["fetch_live"]
    get_recorder, _ = mock_http(scenario.get("http_get", []), scenario.get("http_post", []))
    limiter = asyncio.Semaphore(0)
    adapter = build_live_exchange_adapters(["bybit"], request_limiter=limiter)["bybit"]
    contract = build_contract(scenario["contract"])

    fetch_task = asyncio.create_task(adapter.fetch_live([contract]))
    await asyncio.sleep(0)

    assert get_recorder.call_count == 0
    limiter.release()
    result = await asyncio.wait_for(fetch_task, timeout=1)

    assert set(result) == {contract.id}
    assert get_recorder.call_count == 1
