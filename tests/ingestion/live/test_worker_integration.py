from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.exchanges.dto import FundingPoint
from fundingpulse.ingestion.live.config import LiveWorkerConfig
from fundingpulse.ingestion.live.constants import (
    LIVE_FUNDING_PIPELINE,
    TASK_STATUS_DONE,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_TIMEOUT_ERROR_TYPE,
)
from fundingpulse.ingestion.live.worker import execute_one_live_task
from fundingpulse.models.contract import Contract
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.testing.helpers.data_helpers import create_contract
from fundingpulse.time import utc_datetime
from tests.ingestion.live.helpers import (
    all_ingestion_tasks,
    insert_ingestion_task,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.db]


class FakeLiveExchange(BaseLiveExchange):
    EXCHANGE_ID = "fake"

    def __init__(
        self,
        *,
        rates: dict[str, FundingPoint] | None = None,
        delay_seconds: float | None = None,
        error: Exception | None = None,
    ) -> None:
        self.rates = rates or {}
        self.delay_seconds = delay_seconds
        self.error = error
        self.calls: list[list[Contract]] = []

    def _format_symbol(self, contract: Contract) -> str:
        return contract.asset_name

    async def fetch_live(self, contracts: list[Contract]) -> dict[UUID, FundingPoint]:
        self.calls.append(contracts)
        if self.delay_seconds is not None:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        return {
            contract.id: self.rates[contract.asset_name]
            for contract in contracts
            if contract.asset_name in self.rates
        }


async def _live_points(session: AsyncSession) -> list[LiveFundingPoint]:
    result = await session.execute(
        select(LiveFundingPoint).order_by(col(LiveFundingPoint.contract_id))
    )
    return list(result.scalars().all())


async def test_execute_one_live_task_returns_unclaimed_when_no_pending_task(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    adapter = FakeLiveExchange()

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"bybit": adapter},
    )

    assert result.claimed is False
    assert adapter.calls == []
    assert await all_ingestion_tasks(db_session) == []


async def test_execute_one_live_task_collects_live_rates_and_marks_task_done(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event_logger = logging.getLogger("tests.ingestion.live_worker.success")
    caplog.set_level(logging.INFO, logger=event_logger.name)
    scheduled_for = utc_datetime(2026, 5, 8, 12, 30)
    point_time = utc_datetime(2026, 5, 8, 12, 30, 5)
    contract = await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
    )
    adapter = FakeLiveExchange(rates={"BTC": FundingPoint(rate=0.001, timestamp=point_time)})

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"bybit": adapter},
        event_logger=event_logger,
    )

    tasks = await all_ingestion_tasks(db_session)
    points = await _live_points(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_DONE
    assert [contract.asset_name for contract in adapter.calls[0]] == ["BTC"]
    assert tasks[0].status == TASK_STATUS_DONE
    assert tasks[0].worker_id == "worker-1"
    assert tasks[0].claimed_at is not None
    assert tasks[0].finished_at is not None
    assert [(point.contract_id, point.timestamp, point.funding_rate) for point in points] == [
        (contract.id, point_time, 0.001),
    ]

    events = [getattr(record, "event", None) for record in caplog.records]
    assert "live_task_claimed" in events
    assert "live_fetch_started" in events
    assert "live_fetch_completed" in events
    assert "live_persist_completed" in events
    assert "live_task_completed" in events
    completed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "live_task_completed"
    )
    completed_fields = completed_record.__dict__
    assert completed_fields["pipeline"] == LIVE_FUNDING_PIPELINE
    assert completed_fields["exchange"] == "bybit"
    assert completed_fields["worker_id"] == "worker-1"
    assert completed_fields["scheduled_for"] == "2026-05-08T12:30:00Z"


async def test_execute_one_live_task_executes_task_scheduled_in_the_past(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 1)
    await create_contract(
        db_session,
        asset_name="ETH",
        section_name="okx",
        quote_name="USDT",
        funding_interval=8,
    )
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="okx",
        status=TASK_STATUS_PENDING,
        scheduled_for=scheduled_for,
    )
    adapter = FakeLiveExchange(
        rates={"ETH": FundingPoint(rate=0.002, timestamp=utc_datetime(2026, 5, 8, 12, 2))}
    )

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"okx": adapter},
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.status == TASK_STATUS_DONE
    assert len(adapter.calls) == 1
    assert tasks[0].status == TASK_STATUS_DONE


async def test_execute_one_live_task_marks_adapter_exception_failed(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event_logger = logging.getLogger("tests.ingestion.live_worker.failure")
    caplog.set_level(logging.INFO, logger=event_logger.name)
    await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
    )
    adapter = FakeLiveExchange(error=RuntimeError("boom"))

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"bybit": adapter},
        event_logger=event_logger,
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_FAILED
    assert result.error_type == "RuntimeError"
    assert result.error_message == "boom"
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == "RuntimeError"
    assert tasks[0].error_message == "boom"

    failed_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "live_task_failed"
    )
    failed_fields = failed_record.__dict__
    assert failed_fields["error_type"] == "RuntimeError"
    assert failed_fields["error_message"] == "boom"


async def test_execute_one_live_task_marks_unknown_exchange_failed(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="unsupported",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
    )

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={},
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.status == TASK_STATUS_FAILED
    assert result.error_type == "UnknownLiveExchangeError"
    assert result.error_message == "No live adapter configured for exchange: unsupported"
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == "UnknownLiveExchangeError"


async def test_execute_one_live_task_marks_timeout_failed(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 34),
    )
    adapter = FakeLiveExchange(delay_seconds=1)

    result = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"bybit": adapter},
        config=LiveWorkerConfig(task_timeout=timedelta(milliseconds=10)),
    )

    tasks = await all_ingestion_tasks(db_session)
    assert result.claimed is True
    assert result.status == TASK_STATUS_FAILED
    assert result.error_type == TASK_TIMEOUT_ERROR_TYPE
    assert result.error_message == "Task timed out after 0.01s"
    assert tasks[0].status == TASK_STATUS_FAILED
    assert tasks[0].error_type == TASK_TIMEOUT_ERROR_TYPE
    assert tasks[0].error_message == "Task timed out after 0.01s"


async def test_execute_one_live_task_inserts_live_points_idempotently(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    point_time = utc_datetime(2026, 5, 8, 12, 30, 5)
    contract = await create_contract(
        db_session,
        asset_name="BTC",
        section_name="bybit",
        quote_name="USDT",
        funding_interval=8,
    )
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 30),
    )
    await insert_ingestion_task(
        ingestion_session_factory,
        exchange="bybit",
        status=TASK_STATUS_PENDING,
        scheduled_for=utc_datetime(2026, 5, 8, 12, 31),
    )
    adapter = FakeLiveExchange(rates={"BTC": FundingPoint(rate=0.001, timestamp=point_time)})

    first = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"bybit": adapter},
    )
    second = await execute_one_live_task(
        session_factory=ingestion_session_factory,
        worker_id="worker-1",
        exchange_adapters={"bybit": adapter},
    )

    points = await _live_points(db_session)
    assert first.status == TASK_STATUS_DONE
    assert second.status == TASK_STATUS_DONE
    assert [(point.contract_id, point.timestamp, point.funding_rate) for point in points] == [
        (contract.id, point_time, 0.001),
    ]
