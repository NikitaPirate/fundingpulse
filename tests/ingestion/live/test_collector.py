from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.ingestion.live.collector import collect_live
from fundingpulse.ingestion.live.dto import ClaimedLiveTask
from fundingpulse.models.contract import Contract
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.testing.helpers.data_helpers import create_contract
from fundingpulse.time import utc_datetime
from tests.ingestion.live.helpers import RecordingEventLogger, add_ingestion_task

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


class FakeLiveExchange(BaseLiveExchange):
    EXCHANGE_ID = "fake"

    def __init__(self, rates: dict[str, FundingPoint]) -> None:
        self.rates = rates
        self.calls: list[list[Contract]] = []

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset_name

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        self.calls.append(contracts)
        return {
            contract.id: self.rates[contract.asset_name]
            for contract in contracts
            if contract.asset_name in self.rates
        }


async def _claimed_task(db_session: AsyncSession, exchange: str) -> ClaimedLiveTask:
    created_at = utc_datetime(2026, 5, 8, 12, 34, 1)
    claimed_at = utc_datetime(2026, 5, 8, 12, 34, 2)
    task = await add_ingestion_task(
        db_session,
        exchange=exchange,
        status="running",
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
        created_at=created_at,
        claimed_at=claimed_at,
        worker_id="worker-1",
    )
    return ClaimedLiveTask(
        task_key=task.task_key,
        exchange=exchange,
        scheduled_for=task.scheduled_for,
        payload={},
        created_at=created_at,
        claimed_at=claimed_at,
        worker_id="worker-1",
    )


async def _live_points(session: AsyncSession) -> list[LiveFundingPoint]:
    result = await session.execute(
        select(LiveFundingPoint).order_by(col(LiveFundingPoint.contract_id))
    )
    return list(result.scalars().all())


async def test_collect_live_succeeds_without_active_contracts(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    task = await _claimed_task(db_session, "bybit")
    adapter = FakeLiveExchange({})

    result = await collect_live(
        adapter=adapter,
        task=task,
        session_factory=ingestion_session_factory,
    )

    assert result.expected_contracts == 0
    assert result.received_rates == 0
    assert result.written_points == 0
    assert adapter.calls == []
    assert await _live_points(db_session) == []


async def test_collect_live_writes_partial_adapter_response_and_logs_counts(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    event_logger = RecordingEventLogger()
    task = await _claimed_task(db_session, "bybit")
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
    adapter = FakeLiveExchange({"BTC": FundingPoint(rate=0.001, timestamp=point_time)})

    result = await collect_live(
        adapter=adapter,
        task=task,
        session_factory=ingestion_session_factory,
        event_logger=event_logger,
    )

    points = await _live_points(db_session)
    persist_record = next(
        record for record in event_logger.records if record.event == "live_persist_completed"
    )
    assert result.expected_contracts == 2
    assert result.received_rates == 1
    assert result.written_points == 1
    assert sorted(contract.asset_name for contract in adapter.calls[0]) == ["BTC", "ETH"]
    assert [(point.contract_id, point.timestamp, point.funding_rate) for point in points] == [
        (btc.id, point_time, 0.001),
    ]
    assert persist_record.__dict__["expected_contracts"] == 2
    assert persist_record.__dict__["received_rates"] == 1
    assert persist_record.__dict__["written_points"] == 1
