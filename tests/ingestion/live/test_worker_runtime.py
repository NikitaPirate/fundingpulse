from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from typing import cast

import pytest

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.live.config import LiveWorkerConfig
from fundingpulse.ingestion.live.dto import LiveTaskExecutionResult
from fundingpulse.ingestion.live.runtime import run_live_worker_loop
from fundingpulse.observability.logging import EventLogger
from tests.ingestion.live.helpers import RecordingEventLogger


@pytest.mark.asyncio
async def test_live_worker_loop_executes_one_task_at_a_time() -> None:
    stop_event = asyncio.Event()
    active_calls = 0
    max_active_calls = 0
    calls = 0

    async def execute_task(
        *,
        session_factory: SessionFactory,
        worker_id: str,
        exchange_adapters: Mapping[str, BaseLiveExchange],
        config: LiveWorkerConfig,
        event_logger: EventLogger | None = None,
    ) -> LiveTaskExecutionResult:
        nonlocal active_calls, max_active_calls, calls
        del session_factory, worker_id, exchange_adapters, config, event_logger
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        await asyncio.sleep(0)
        active_calls -= 1
        calls += 1
        if calls == 3:
            stop_event.set()
        return LiveTaskExecutionResult(claimed=True)

    await run_live_worker_loop(
        session_factory=cast(SessionFactory, object()),
        worker_id="worker-1",
        exchange_adapters={},
        config=LiveWorkerConfig(poll_interval=timedelta(milliseconds=1)),
        stop_event=stop_event,
        execute_task=execute_task,
    )

    assert calls == 3
    assert max_active_calls == 1


@pytest.mark.asyncio
async def test_live_worker_loop_sleeps_when_no_task_is_claimed() -> None:
    stop_event = asyncio.Event()
    sleep_seconds: list[float] = []

    async def execute_task(
        *,
        session_factory: SessionFactory,
        worker_id: str,
        exchange_adapters: Mapping[str, BaseLiveExchange],
        config: LiveWorkerConfig,
        event_logger: EventLogger | None = None,
    ) -> LiveTaskExecutionResult:
        del session_factory, worker_id, exchange_adapters, config, event_logger
        return LiveTaskExecutionResult(claimed=False)

    async def sleep(seconds: float) -> None:
        sleep_seconds.append(seconds)
        stop_event.set()

    await run_live_worker_loop(
        session_factory=cast(SessionFactory, object()),
        worker_id="worker-1",
        exchange_adapters={},
        config=LiveWorkerConfig(poll_interval=timedelta(milliseconds=25)),
        stop_event=stop_event,
        execute_task=execute_task,
        sleep=sleep,
    )

    assert sleep_seconds == [0.025]


@pytest.mark.asyncio
async def test_live_worker_loop_continues_after_iteration_error() -> None:
    stop_event = asyncio.Event()
    event_logger = RecordingEventLogger()
    calls = 0
    sleeps = 0

    async def execute_task(
        *,
        session_factory: SessionFactory,
        worker_id: str,
        exchange_adapters: Mapping[str, BaseLiveExchange],
        config: LiveWorkerConfig,
        event_logger: EventLogger | None = None,
    ) -> LiveTaskExecutionResult:
        nonlocal calls
        del session_factory, worker_id, exchange_adapters, config, event_logger
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        stop_event.set()
        return LiveTaskExecutionResult(claimed=True)

    async def sleep(seconds: float) -> None:
        nonlocal sleeps
        del seconds
        sleeps += 1

    await run_live_worker_loop(
        session_factory=cast(SessionFactory, object()),
        worker_id="worker-1",
        exchange_adapters={},
        config=LiveWorkerConfig(poll_interval=timedelta(milliseconds=1)),
        stop_event=stop_event,
        event_logger=event_logger,
        execute_task=execute_task,
        sleep=sleep,
    )

    assert calls == 2
    assert sleeps == 1
    failed_record = next(
        record for record in event_logger.records if record.event == "live_worker_iteration_failed"
    )
    failed_fields = failed_record.__dict__
    assert failed_fields["error_type"] == "RuntimeError"
    assert failed_fields["worker_id"] == "worker-1"
