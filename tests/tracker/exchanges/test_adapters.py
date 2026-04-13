"""Parametrized parsing tests for all exchange adapters.

One test module, three parametrized tests, 15 fixture files.
Test code is shared; only data varies per adapter.

Adding a new adapter: create fixtures/{exchange_id}.json, zero test code changes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.time import utc_datetime
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ADAPTER_IDS = sorted(EXCHANGES.keys())

# Fixed timestamps used across all fetch_history tests.
# Using dates far in the past ensures all adapters have meaningful time windows.
AFTER_TS = utc_datetime(2024, 1, 1)
BEFORE_TS = utc_datetime(2024, 1, 2)


# ---------------------------------------------------------------------------
# Helpers (not fixtures — plain functions)
# ---------------------------------------------------------------------------


def load_fixture(exchange_id: str) -> dict[str, Any]:
    filename = exchange_id.replace("-", "_") + ".json"
    return json.loads((FIXTURES_DIR / filename).read_text())


def build_contract(defn: dict[str, Any]) -> Contract:
    """Build a Contract with attached Asset for adapter tests — no DB required.

    Mirrors verify_exchange.py:_build_contract_for_checks.
    Contract.id is auto-generated via default_factory=uuid.uuid4.
    """
    contract = Contract(
        asset_name=defn["asset_name"],
        quote_name=defn["quote_name"],
        section_name=defn["section_name"],
        funding_interval=defn["funding_interval"],
    )
    contract.asset = Asset(name=defn["asset_name"])
    return contract


def make_adapter(exchange_id: str, state: dict[str, Any] | None = None) -> BaseExchange:
    """Create a fresh adapter instance, optionally pre-seeded with instance state.

    Fresh instance per test avoids contamination from mutable instance state
    (e.g. lighter._asset_to_id, paradex._live_cache).
    """
    adapter = EXCHANGES[exchange_id]()
    if state:
        for key, value in state.items():
            setattr(adapter, key, value)
    return adapter


def assert_aware_utc_timestamp(value: object) -> None:
    assert hasattr(value, "tzinfo")
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


# ---------------------------------------------------------------------------
# WebSocket mock for lighter.fetch_live
# ---------------------------------------------------------------------------


class _MockWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = iter(messages)

    async def send(self, data: str) -> None:
        pass

    async def recv(self) -> str:
        return next(self._messages)


class _MockWsConnection:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages

    async def __aenter__(self) -> _MockWebSocket:
        return _MockWebSocket(self._messages)

    async def __aexit__(self, *args: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exchange_id", ADAPTER_IDS)
@pytest.mark.asyncio
async def test_get_contracts(exchange_id: str, mock_http: Callable[..., object]) -> None:
    """get_contracts() returns a non-empty list of valid ContractInfo objects."""
    fixture = load_fixture(exchange_id)
    scenario = fixture["get_contracts"]
    mock_http(scenario.get("http_get", []), scenario.get("http_post", []))

    adapter = make_adapter(exchange_id)
    contracts = await adapter.get_contracts()

    assert len(contracts) >= scenario["expected_count_gte"]
    assert all(isinstance(c, ContractInfo) for c in contracts)
    assert all(c.section_name == adapter.EXCHANGE_ID for c in contracts)
    assert all(c.funding_interval > 0 for c in contracts)

    if sample := scenario.get("expected_sample"):
        matched = [c for c in contracts if c.asset_name == sample["asset_name"]]
        assert matched, f"Expected contract {sample['asset_name']!r} not found in result"
        c = matched[0]
        assert c.quote == sample["quote"]
        assert c.funding_interval == sample["funding_interval"]


@pytest.mark.parametrize("exchange_id", ADAPTER_IDS)
@pytest.mark.asyncio
async def test_fetch_history(exchange_id: str, mock_http: Callable[..., object]) -> None:
    """fetch_history returns a list of valid FundingPoint objects.

    Calls fetch_history_after by default.
    For adapters with use_before=true (paradex), calls fetch_history_before instead,
    because their _fetch_history raises NotImplementedError.
    """
    fixture = load_fixture(exchange_id)
    scenario = fixture["fetch_history"]
    mock_http(scenario.get("http_get", []), scenario.get("http_post", []))

    contract = build_contract(scenario["contract"])
    adapter = make_adapter(exchange_id, scenario.get("adapter_state"))

    if scenario.get("use_before"):
        points = await adapter.fetch_history_before(contract, BEFORE_TS)
    else:
        points = await adapter.fetch_history_after(contract, AFTER_TS)

    assert len(points) >= scenario["expected_count_gte"]
    assert all(isinstance(p, FundingPoint) for p in points)
    assert all(isinstance(p.rate, float) for p in points)
    for point in points:
        assert_aware_utc_timestamp(point.timestamp)


@pytest.mark.parametrize("exchange_id", ADAPTER_IDS)
@pytest.mark.asyncio
async def test_fetch_live(
    exchange_id: str, mock_http: Callable[..., object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """fetch_live returns a dict of Contract → FundingPoint with valid values."""
    fixture = load_fixture(exchange_id)
    scenario = fixture["fetch_live"]
    mock_http(scenario.get("http_get", []), scenario.get("http_post", []))

    if ws_messages := scenario.get("ws_responses"):
        monkeypatch.setattr(
            "websockets.connect",
            lambda url, **kwargs: _MockWsConnection(ws_messages),
        )

    contract = build_contract(scenario["contract"])
    adapter = make_adapter(exchange_id, scenario.get("adapter_state"))

    result = await adapter.fetch_live([contract])

    assert len(result) >= scenario["expected_count_gte"]
    assert all(isinstance(v, FundingPoint) for v in result.values())
    assert all(isinstance(v.rate, float) for v in result.values())
    for point in result.values():
        assert_aware_utc_timestamp(point.timestamp)
