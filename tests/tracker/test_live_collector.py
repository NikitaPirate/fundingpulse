from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import col

from fundingpulse.db import SessionFactory
from fundingpulse.models.contract import Contract
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.observability.logging import EventLogger
from fundingpulse.testing.helpers.data_helpers import create_contract
from fundingpulse.time import utc_datetime
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint
from fundingpulse.tracker.orchestration.live_collector import (
    LiveCollectionResult,
    collect_live,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


class FakeExchange(BaseExchange):
    EXCHANGE_ID = "fake"
    _FETCH_STEP = 8

    def __init__(
        self,
        rates: dict[str, FundingPoint] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        super().__init__()
        self.rates = rates or {}
        self.error = error
        self.calls: list[list[Contract]] = []

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset_name

    async def get_contracts(self) -> list[ExchangeContractListing]:
        return []

    async def _fetch_history(
        self, contract: Contract, start_ms: int, end_ms: int
    ) -> list[FundingPoint]:
        raise NotImplementedError

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        self.calls.append(contracts)
        if self.error is not None:
            raise self.error
        return {
            contract.id: self.rates[contract.asset_name]
            for contract in contracts
            if contract.asset_name in self.rates
        }


@dataclass(slots=True)
class RecordedEvent:
    event: str
    fields: dict[str, object]


class RecordingEventLogger:
    def __init__(self) -> None:
        self.records: list[RecordedEvent] = []

    def bind(self, **fields: object) -> EventLogger:
        return BoundRecordingEventLogger(self, fields)

    def info(self, event: str, **fields: object) -> object:
        self.records.append(RecordedEvent(event, fields))
        return None

    def debug(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def warning(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def error(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)

    def exception(self, event: str, **fields: object) -> object:
        return self.info(event, **fields)


class BoundRecordingEventLogger:
    def __init__(self, parent: RecordingEventLogger, bound_fields: dict[str, object]) -> None:
        self._parent = parent
        self._bound_fields = bound_fields

    def bind(self, **fields: object) -> EventLogger:
        return BoundRecordingEventLogger(self._parent, {**self._bound_fields, **fields})

    def info(self, event: str, **fields: object) -> object:
        self._parent.records.append(RecordedEvent(event, {**self._bound_fields, **fields}))
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


async def _live_points(session: AsyncSession) -> list[LiveFundingPoint]:
    result = await session.execute(
        select(LiveFundingPoint).order_by(col(LiveFundingPoint.contract_id))
    )
    return list(result.scalars().all())


def _event(logger: RecordingEventLogger, name: str) -> RecordedEvent:
    return next(record for record in logger.records if record.event == name)


async def test_collect_live_succeeds_without_active_contracts(
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    event_logger = RecordingEventLogger()
    adapter = FakeExchange()

    result = await collect_live(
        adapter=adapter,
        section_name="bybit",
        db=tracker_session_factory,
        event_logger=event_logger,
    )

    assert result == LiveCollectionResult(
        expected_contracts=0,
        received_rates=0,
        written_points=0,
    )
    assert adapter.calls == []
    assert await _live_points(db_session) == []
    completed = _event(event_logger, "live_collection_completed")
    assert completed.fields["workflow"] == "live"
    assert completed.fields["exchange"] == "bybit"
    assert completed.fields["expected_contracts"] == 0
    assert completed.fields["received_rates"] == 0
    assert completed.fields["written_points"] == 0
    assert isinstance(completed.fields["duration_seconds"], float)


async def test_collect_live_writes_partial_adapter_response_and_logs_counts(
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    event_logger = RecordingEventLogger()
    btc = await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    await create_contract(
        db_session,
        asset_name="ETH",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    deprecated = await create_contract(
        db_session,
        asset_name="SOL",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    deprecated.deprecated = True
    await db_session.commit()

    point_time = utc_datetime(2026, 5, 8, 12, 34, 5)
    adapter = FakeExchange({"BTC": FundingPoint(rate=0.001, timestamp=point_time)})

    result = await collect_live(
        adapter=adapter,
        section_name="bybit",
        db=tracker_session_factory,
        event_logger=event_logger,
    )

    points = await _live_points(db_session)
    fetch_record = _event(event_logger, "live_fetch_completed")
    persist_record = _event(event_logger, "live_persist_completed")
    completed = _event(event_logger, "live_collection_completed")
    assert result == LiveCollectionResult(
        expected_contracts=2,
        received_rates=1,
        written_points=1,
    )
    assert sorted(contract.asset_name for contract in adapter.calls[0]) == ["BTC", "ETH"]
    assert [(point.contract_id, point.timestamp, point.funding_rate) for point in points] == [
        (btc.id, point_time, 0.001),
    ]
    assert fetch_record.fields["exchange"] == "bybit"
    assert fetch_record.fields["workflow"] == "live"
    assert fetch_record.fields["expected_contracts"] == 2
    assert fetch_record.fields["received_rates"] == 1
    assert isinstance(fetch_record.fields["fetch_duration_seconds"], float)
    assert persist_record.fields["attempted_points"] == 1
    assert persist_record.fields["written_points"] == 1
    assert isinstance(persist_record.fields["persist_duration_seconds"], float)
    assert completed.fields["written_points"] == 1
    assert isinstance(completed.fields["duration_seconds"], float)


async def test_collect_live_reports_duplicate_conflict_insert_count(
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    contract = await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    point_time = utc_datetime(2026, 5, 8, 12, 34, 5)
    db_session.add(
        LiveFundingPoint(
            contract_id=contract.id,
            timestamp=point_time,
            funding_rate=0.001,
        )
    )
    await db_session.commit()

    event_logger = RecordingEventLogger()
    adapter = FakeExchange({"BTC": FundingPoint(rate=0.001, timestamp=point_time)})

    result = await collect_live(
        adapter=adapter,
        section_name="bybit",
        db=tracker_session_factory,
        event_logger=event_logger,
    )

    assert result == LiveCollectionResult(
        expected_contracts=1,
        received_rates=1,
        written_points=0,
    )
    persist_record = _event(event_logger, "live_persist_completed")
    assert persist_record.fields["attempted_points"] == 1
    assert persist_record.fields["written_points"] == 0


async def test_collect_live_swallows_adapter_failure_and_logs_failed_event(
    tracker_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    event_logger = RecordingEventLogger()
    adapter = FakeExchange(error=RuntimeError("exchange unavailable"))

    result = await collect_live(
        adapter=adapter,
        section_name="bybit",
        db=tracker_session_factory,
        event_logger=event_logger,
    )

    assert result == LiveCollectionResult(
        expected_contracts=1,
        received_rates=0,
        written_points=0,
    )
    failed = _event(event_logger, "live_collection_failed")
    assert failed.fields["workflow"] == "live"
    assert failed.fields["exchange"] == "bybit"
    assert failed.fields["expected_contracts"] == 1
    assert failed.fields["received_rates"] == 0
    assert failed.fields["written_points"] == 0
    assert failed.fields["error_type"] == "RuntimeError"
    assert failed.fields["error_message"] == "exchange unavailable"
    assert isinstance(failed.fields["duration_seconds"], float)
