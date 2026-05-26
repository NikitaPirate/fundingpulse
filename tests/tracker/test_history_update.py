from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import col

from fundingpulse.db import SessionFactory
from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.observability.logging import EventLogger
from fundingpulse.testing.helpers.data_helpers import create_contract
from fundingpulse.time import UtcDateTime, utc_datetime
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint
from fundingpulse.tracker.orchestration.history_update import (
    HistoryUpdateResult,
    run_history_update,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.db]

_SECTION = "history_update_ex"


class _HistoryUpdateExchange(BaseExchange):
    EXCHANGE_ID = _SECTION
    _FETCH_STEP = 8

    def __init__(
        self,
        responses: dict[str, list[FundingPoint]] | None = None,
        *,
        errors: dict[str, Exception] | None = None,
        block: asyncio.Event | None = None,
        block_assets: set[str] | None = None,
    ) -> None:
        super().__init__()
        self.responses = responses or {}
        self.errors = errors or {}
        self.block = block
        self.block_assets = block_assets
        self.after_calls: list[tuple[str, UtcDateTime]] = []
        self.cancelled_assets: list[str] = []

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset_name

    async def get_contracts(self) -> list[ExchangeContractListing]:
        return []

    async def _fetch_history(
        self,
        contract: Contract,
        start_ms: int,
        end_ms: int,
    ) -> list[FundingPoint]:
        raise NotImplementedError

    async def fetch_history_after(
        self,
        contract: Contract,
        after_timestamp: UtcDateTime,
    ) -> list[FundingPoint]:
        self.after_calls.append((contract.asset_name, after_timestamp))
        if self.block is not None and (
            self.block_assets is None or contract.asset_name in self.block_assets
        ):
            try:
                await self.block.wait()
            except asyncio.CancelledError:
                self.cancelled_assets.append(contract.asset_name)
                raise
        if contract.asset_name in self.errors:
            raise self.errors[contract.asset_name]
        return list(self.responses.get(contract.asset_name, []))


@dataclass(slots=True)
class _RecordedEvent:
    event: str
    fields: dict[str, object]


class _RecordingEventLogger:
    def __init__(self) -> None:
        self.records: list[_RecordedEvent] = []

    def bind(self, **fields: object) -> EventLogger:
        return _BoundRecordingEventLogger(self, fields)

    def info(self, event: str, **fields: object) -> object:
        self.records.append(_RecordedEvent(event, fields))
        return None

    def debug(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def warning(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def error(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def exception(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)


class _BoundRecordingEventLogger:
    def __init__(self, parent: _RecordingEventLogger, fields: dict[str, object]) -> None:
        self._parent = parent
        self._fields = fields

    def bind(self, **fields: object) -> EventLogger:
        return _BoundRecordingEventLogger(self._parent, {**self._fields, **fields})

    def info(self, event: str, **fields: object) -> object:
        self._parent.records.append(_RecordedEvent(event, {**self._fields, **fields}))
        return None

    def debug(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def warning(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def error(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def exception(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)


@pytest.fixture
def tracker_session_factory(
    engine: AsyncEngine,
    db_session_kwargs: dict[str, object],
) -> SessionFactory:
    return async_sessionmaker(engine, **db_session_kwargs)  # type: ignore[return-value, arg-type]


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


async def _historical_points(session: AsyncSession) -> list[HistoricalFundingPoint]:
    result = await session.execute(
        select(HistoricalFundingPoint).order_by(
            col(HistoricalFundingPoint.contract_id),
            col(HistoricalFundingPoint.timestamp),
        )
    )
    return list(result.scalars().all())


def _event(logger: _RecordingEventLogger, name: str) -> _RecordedEvent:
    return next(record for record in logger.records if record.event == name)


async def test_history_update_succeeds_without_active_contracts(
    tracker_session_factory: SessionFactory,
) -> None:
    event_logger = _RecordingEventLogger()
    adapter = _HistoryUpdateExchange()

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
        event_logger=event_logger,
    )

    assert result == HistoryUpdateResult()
    assert adapter.after_calls == []
    completed = _event(event_logger, "history_update_completed")
    assert completed.fields["workflow"] == "history_update"
    assert completed.fields["exchange"] == _SECTION
    assert completed.fields["contracts_total"] == 0
    assert completed.fields["points_written"] == 0
    assert isinstance(completed.fields["duration_seconds"], float)


async def test_history_update_skips_fresh_contract_before_api_call(
    monkeypatch: pytest.MonkeyPatch,
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 0, 5)
    monkeypatch.setattr("fundingpulse.tracker.orchestration.history_update.utc_now", lambda: now)
    contract = await create_contract(
        db_session,
        asset_name="BTC",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    await _set_state(
        db_session,
        contract,
        history_synced=False,
        oldest_timestamp=now - timedelta(days=1),
        newest_timestamp=now - timedelta(hours=1),
    )
    adapter = _HistoryUpdateExchange(
        {"BTC": [FundingPoint(rate=0.001, timestamp=now)]},
    )

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
    )

    assert result == HistoryUpdateResult(contracts_total=1, contracts_skipped=1)
    assert adapter.after_calls == []


async def test_history_update_persists_due_contract_from_newest_bound(
    monkeypatch: pytest.MonkeyPatch,
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 0, 5)
    monkeypatch.setattr("fundingpulse.tracker.orchestration.history_update.utc_now", lambda: now)
    contract = await create_contract(
        db_session,
        asset_name="ETH",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    newest = utc_datetime(2026, 5, 8, 0)
    state = await _set_state(
        db_session,
        contract,
        history_synced=True,
        oldest_timestamp=newest - timedelta(days=30),
        newest_timestamp=newest,
    )
    point = FundingPoint(rate=0.002, timestamp=utc_datetime(2026, 5, 8, 8))
    adapter = _HistoryUpdateExchange({"ETH": [point]})

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
    )

    await db_session.refresh(state)
    points = await _historical_points(db_session)
    assert result == HistoryUpdateResult(
        contracts_total=1,
        contracts_attempted=1,
        contracts_updated=1,
        points_fetched=1,
        points_written=1,
    )
    assert adapter.after_calls == [("ETH", newest + timedelta(seconds=1))]
    assert [(point.contract_id, point.timestamp, point.funding_rate) for point in points] == [
        (contract.id, point.timestamp, point.rate),
    ]
    assert state.newest_timestamp == point.timestamp


async def test_history_update_contract_without_bounds_fetches_from_current_hour(
    monkeypatch: pytest.MonkeyPatch,
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 34, 5)
    monkeypatch.setattr("fundingpulse.tracker.orchestration.history_update.utc_now", lambda: now)
    contract = await create_contract(
        db_session,
        asset_name="SOL",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    state = await _set_state(db_session, contract, history_synced=False)
    point = FundingPoint(rate=0.003, timestamp=utc_datetime(2026, 5, 8, 12))
    adapter = _HistoryUpdateExchange({"SOL": [point]})

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
    )

    await db_session.refresh(state)
    assert result.points_written == 1
    assert adapter.after_calls == [("SOL", utc_datetime(2026, 5, 8, 11, 59, 59))]
    assert state.history_synced is False
    assert state.oldest_timestamp == point.timestamp
    assert state.newest_timestamp == point.timestamp


async def test_history_update_isolates_contract_failure(
    monkeypatch: pytest.MonkeyPatch,
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 0, 5)
    monkeypatch.setattr("fundingpulse.tracker.orchestration.history_update.utc_now", lambda: now)
    btc = await create_contract(
        db_session,
        asset_name="BTC",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    eth = await create_contract(
        db_session,
        asset_name="ETH",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    newest = utc_datetime(2026, 5, 8, 0)
    await _set_state(
        db_session,
        btc,
        history_synced=True,
        oldest_timestamp=newest,
        newest_timestamp=newest,
    )
    await _set_state(
        db_session,
        eth,
        history_synced=True,
        oldest_timestamp=newest,
        newest_timestamp=newest,
    )
    btc_point = FundingPoint(rate=0.001, timestamp=utc_datetime(2026, 5, 8, 8))
    event_logger = _RecordingEventLogger()
    adapter = _HistoryUpdateExchange(
        {"BTC": [btc_point]},
        errors={"ETH": RuntimeError("exchange unavailable")},
    )

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
        event_logger=event_logger,
    )

    points = await _historical_points(db_session)
    failed = _event(event_logger, "history_update_contract_failed")
    completed = _event(event_logger, "history_update_completed")
    assert result == HistoryUpdateResult(
        contracts_total=2,
        contracts_attempted=2,
        contracts_updated=1,
        contracts_failed=1,
        points_fetched=1,
        points_written=1,
    )
    assert {asset for asset, _ in adapter.after_calls} == {"BTC", "ETH"}
    assert [(point.contract_id, point.timestamp) for point in points] == [
        (btc.id, btc_point.timestamp),
    ]
    assert failed.fields["asset"] == "ETH"
    assert failed.fields["error_type"] == "RuntimeError"
    assert completed.fields["contracts_failed"] == 1


async def test_history_update_reports_duplicate_conflict_write_count(
    monkeypatch: pytest.MonkeyPatch,
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 0, 5)
    monkeypatch.setattr("fundingpulse.tracker.orchestration.history_update.utc_now", lambda: now)
    contract = await create_contract(
        db_session,
        asset_name="DOGE",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    newest = utc_datetime(2026, 5, 8, 0)
    duplicate_timestamp = utc_datetime(2026, 5, 8, 8)
    state = await _set_state(
        db_session,
        contract,
        history_synced=True,
        oldest_timestamp=newest,
        newest_timestamp=newest,
    )
    db_session.add(
        HistoricalFundingPoint(
            contract_id=contract.id,
            timestamp=duplicate_timestamp,
            funding_rate=0.004,
        )
    )
    await db_session.commit()
    adapter = _HistoryUpdateExchange(
        {"DOGE": [FundingPoint(rate=0.004, timestamp=duplicate_timestamp)]},
    )

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
    )

    await db_session.refresh(state)
    assert result == HistoryUpdateResult(
        contracts_total=1,
        contracts_attempted=1,
        points_fetched=1,
        points_written=0,
    )
    assert len(await _historical_points(db_session)) == 1
    assert state.newest_timestamp == duplicate_timestamp


async def test_history_update_timeout_is_logged_and_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    now = utc_datetime(2026, 5, 8, 12, 0, 5)
    monkeypatch.setattr("fundingpulse.tracker.orchestration.history_update.utc_now", lambda: now)
    btc = await create_contract(
        db_session,
        asset_name="BTC",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    xrp = await create_contract(
        db_session,
        asset_name="XRP",
        section_name=_SECTION,
        quote_name="USDT",
        funding_interval=8,
    )
    newest = utc_datetime(2026, 5, 8, 0)
    await _set_state(
        db_session,
        btc,
        history_synced=True,
        oldest_timestamp=newest,
        newest_timestamp=newest,
    )
    await _set_state(
        db_session,
        xrp,
        history_synced=True,
        oldest_timestamp=newest,
        newest_timestamp=newest,
    )
    btc_point = FundingPoint(rate=0.001, timestamp=utc_datetime(2026, 5, 8, 8))
    event_logger = _RecordingEventLogger()
    adapter = _HistoryUpdateExchange(
        {"BTC": [btc_point]},
        block=asyncio.Event(),
        block_assets={"XRP"},
    )

    result = await run_history_update(
        adapter=adapter,
        section_name=_SECTION,
        db=tracker_session_factory,
        event_logger=event_logger,
        timeout_seconds=0.2,
    )

    failed = _event(event_logger, "history_update_failed")
    assert result == HistoryUpdateResult(
        contracts_total=2,
        contracts_attempted=2,
        contracts_updated=1,
        points_fetched=1,
        points_written=1,
    )
    assert failed.fields["workflow"] == "history_update"
    assert failed.fields["exchange"] == _SECTION
    assert failed.fields["error_type"] == "TimeoutError"
    assert failed.fields["error_message"] == "timed out after 0.2s"
    assert failed.fields["points_written"] == 1
    assert isinstance(failed.fields["duration_seconds"], float)
    assert adapter.cancelled_assets == ["XRP"]
