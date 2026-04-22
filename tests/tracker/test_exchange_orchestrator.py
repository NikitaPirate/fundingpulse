from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import col

from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.testing.helpers.data_helpers import create_contract
from fundingpulse.time import UtcDateTime, utc_now
from fundingpulse.tracker.contracts import TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo, FundingPoint
from fundingpulse.tracker.orchestration.history_sync import process_contracts
from fundingpulse.tracker.orchestration.section_logger import make_section_logger
from fundingpulse.tracker.queries.contracts import get_active_by_section_with_history_state


class _FakeExchange(BaseExchange):
    EXCHANGE_ID = "orchestrator_ex"
    _FETCH_STEP = 8

    def __init__(
        self,
        *,
        before_responses: list[list[FundingPoint]] | None = None,
        after_responses: list[list[FundingPoint]] | None = None,
    ) -> None:
        super().__init__()
        self.before_responses = before_responses or []
        self.after_responses = after_responses or []
        self.before_calls: list[UtcDateTime | None] = []
        self.after_calls: list[UtcDateTime] = []

    def _format_symbol(self, contract: TrackedContract) -> str:
        return contract.asset_name

    async def get_contracts(self) -> list[ContractInfo]:
        return []

    async def _fetch_history(
        self, contract: TrackedContract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        raise NotImplementedError

    async def fetch_history_before(
        self, contract: TrackedContract, before_timestamp: UtcDateTime | None
    ) -> list[FundingPoint]:
        self.before_calls.append(before_timestamp)
        if not self.before_responses:
            raise AssertionError("Unexpected fetch_history_before call")
        return self.before_responses.pop(0)

    async def fetch_history_after(
        self, contract: TrackedContract, after_timestamp: UtcDateTime
    ) -> list[FundingPoint]:
        self.after_calls.append(after_timestamp)
        if not self.after_responses:
            raise AssertionError("Unexpected fetch_history_after call")
        return self.after_responses.pop(0)


def _session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def _load_contracts(session: AsyncSession, section_name: str) -> list[Contract]:
    contracts = await get_active_by_section_with_history_state(session, section_name)
    return list(contracts)


async def _set_state(
    session: AsyncSession,
    contract: Contract,
    *,
    history_synced: bool,
    oldest_timestamp: UtcDateTime | None = None,
    newest_timestamp: UtcDateTime | None = None,
) -> ContractHistoryState:
    state = await session.get(ContractHistoryState, contract.id)
    assert state is not None
    state.history_synced = history_synced
    state.oldest_timestamp = oldest_timestamp
    state.newest_timestamp = newest_timestamp
    await session.commit()
    return state


async def _run(
    engine: AsyncEngine,
    exchange: _FakeExchange,
    contracts: list[Contract],
) -> list[tuple[int, int]]:
    return await process_contracts(
        adapter=exchange,
        contracts=contracts,
        db=_session_factory(engine),
        logger=make_section_logger(__name__, exchange.EXCHANGE_ID),
    )


@pytest.mark.asyncio
async def test_fresh_synced_contract_is_skipped_before_api_call(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(
        db_session,
        asset_name="BTC",
        section_name=_FakeExchange.EXCHANGE_ID,
        quote_name="USDT",
        funding_interval=8,
    )
    await _set_state(
        db_session,
        contract,
        history_synced=True,
        oldest_timestamp=utc_now() - timedelta(days=30),
        newest_timestamp=utc_now(),
    )

    exchange = _FakeExchange(after_responses=[[FundingPoint(rate=0.01, timestamp=utc_now())]])
    results = await _run(
        engine, exchange, await _load_contracts(db_session, _FakeExchange.EXCHANGE_ID)
    )

    assert results == [(0, 0)]
    assert exchange.after_calls == []


@pytest.mark.asyncio
async def test_due_synced_contract_updates_from_state_cursor(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(
        db_session,
        asset_name="ETH",
        section_name=_FakeExchange.EXCHANGE_ID,
        quote_name="USDT",
        funding_interval=8,
    )
    newest = utc_now() - timedelta(hours=12)
    point = FundingPoint(rate=0.001, timestamp=utc_now() - timedelta(hours=1))
    state = await _set_state(
        db_session,
        contract,
        history_synced=True,
        oldest_timestamp=newest - timedelta(days=10),
        newest_timestamp=newest,
    )
    exchange = _FakeExchange(after_responses=[[point]])
    results = await _run(
        engine, exchange, await _load_contracts(db_session, _FakeExchange.EXCHANGE_ID)
    )
    await db_session.refresh(state)
    record = (
        await db_session.execute(
            select(HistoricalFundingPoint).where(
                col(HistoricalFundingPoint.contract_id) == contract.id
            )
        )
    ).scalar_one()

    assert results == [(1, 1)]
    assert exchange.after_calls == [newest + timedelta(seconds=1)]
    assert record.timestamp == point.timestamp
    assert state.newest_timestamp == point.timestamp


@pytest.mark.asyncio
async def test_unsynced_contract_syncs_from_state_cursor(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(
        db_session,
        asset_name="SOL",
        section_name=_FakeExchange.EXCHANGE_ID,
        quote_name="USDT",
        funding_interval=8,
    )
    current_oldest = utc_now() - timedelta(days=5)
    older_point = FundingPoint(rate=0.002, timestamp=current_oldest - timedelta(hours=8))
    db_session.add(
        HistoricalFundingPoint(
            contract_id=contract.id,
            timestamp=current_oldest,
            funding_rate=0.001,
        )
    )
    state = await _set_state(
        db_session,
        contract,
        history_synced=False,
        oldest_timestamp=current_oldest,
        newest_timestamp=current_oldest,
    )
    exchange = _FakeExchange(before_responses=[[older_point], []])
    results = await _run(
        engine, exchange, await _load_contracts(db_session, _FakeExchange.EXCHANGE_ID)
    )
    await db_session.refresh(state)

    assert results == [(1, 1)]
    assert exchange.before_calls == [
        current_oldest - timedelta(seconds=1),
        older_point.timestamp - timedelta(seconds=1),
    ]
    assert state.history_synced is True
    assert state.oldest_timestamp == older_point.timestamp
    assert state.newest_timestamp == current_oldest


@pytest.mark.asyncio
async def test_empty_sync_response_without_points_keeps_history_unsynced(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(
        db_session,
        asset_name="XRP",
        section_name=_FakeExchange.EXCHANGE_ID,
        quote_name="USDT",
        funding_interval=8,
    )
    state = await _set_state(db_session, contract, history_synced=False)
    exchange = _FakeExchange(before_responses=[[]])
    results = await _run(
        engine, exchange, await _load_contracts(db_session, _FakeExchange.EXCHANGE_ID)
    )
    await db_session.refresh(state)

    assert results == [(0, 0)]
    assert exchange.before_calls == [None]
    assert state.history_synced is False
    assert state.oldest_timestamp is None
    assert state.newest_timestamp is None

    first_point = FundingPoint(rate=0.003, timestamp=utc_now() - timedelta(hours=1))
    exchange = _FakeExchange(before_responses=[[first_point], []])
    results = await _run(
        engine, exchange, await _load_contracts(db_session, _FakeExchange.EXCHANGE_ID)
    )
    await db_session.refresh(state)

    assert results == [(1, 1)]
    assert exchange.before_calls == [None, first_point.timestamp - timedelta(seconds=1)]
    assert state.history_synced is True
    assert state.oldest_timestamp == first_point.timestamp
    assert state.newest_timestamp == first_point.timestamp


@pytest.mark.asyncio
async def test_empty_sync_response_with_existing_bounds_marks_history_synced(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(
        db_session,
        asset_name="ADA",
        section_name=_FakeExchange.EXCHANGE_ID,
        quote_name="USDT",
        funding_interval=8,
    )
    timestamp = utc_now() - timedelta(days=1)
    state = await _set_state(
        db_session,
        contract,
        history_synced=False,
        oldest_timestamp=timestamp,
        newest_timestamp=timestamp,
    )
    exchange = _FakeExchange(before_responses=[[]])
    results = await _run(
        engine, exchange, await _load_contracts(db_session, _FakeExchange.EXCHANGE_ID)
    )
    await db_session.refresh(state)

    assert results == [(0, 0)]
    assert exchange.before_calls == [timestamp - timedelta(seconds=1)]
    assert state.history_synced is True
