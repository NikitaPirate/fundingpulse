from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, NoReturn, cast

import pytest

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.ingestion.live.constants import LIVE_FUNDING_PIPELINE
from fundingpulse.ingestion.live.dto import LiveEnqueueTick
from fundingpulse.ingestion.live.enqueuer import (
    build_live_funding_task_key,
    enqueue_live_funding_tick,
)
from fundingpulse.time import utc_datetime


class FailingSessionFactory:
    def begin(self) -> NoReturn:
        raise RuntimeError("database unavailable")


def test_live_enqueue_tick_uses_exact_now_for_stale_threshold() -> None:
    now = utc_datetime(2026, 5, 8, 12, 34, 56)
    config = LiveEnqueuerConfig(
        task_timeout=timedelta(seconds=45),
        stale_running_grace=timedelta(seconds=15),
    )

    tick = LiveEnqueueTick.from_instant(now, config)

    assert tick.now == now
    assert tick.scheduled_for == utc_datetime(2026, 5, 8, 12, 34)
    assert tick.stale_before == utc_datetime(2026, 5, 8, 12, 33, 56)


def test_live_funding_task_key_is_stable() -> None:
    scheduled_for = utc_datetime(2026, 5, 8, 12, 34)

    assert (
        build_live_funding_task_key("bybit", scheduled_for)
        == "live_funding_snapshot:bybit:2026-05-08T12:34:00Z"
    )


@pytest.mark.asyncio
async def test_enqueue_live_funding_tick_logs_failed_event_for_execution_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event_logger = logging.getLogger("tests.ingestion.live_enqueuer.failure")
    caplog.set_level(logging.INFO, logger=event_logger.name)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await enqueue_live_funding_tick(
            session_factory=cast(SessionFactory, FailingSessionFactory()),
            exchanges=["bybit"],
            now=utc_datetime(2026, 5, 8, 12, 34, 56),
            event_logger=event_logger,
        )

    failed_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "live_enqueue_failed"
    )
    failed_fields = cast(dict[str, Any], failed_record.__dict__)
    assert failed_fields["pipeline"] == LIVE_FUNDING_PIPELINE
    assert failed_fields["scheduled_for"] == "2026-05-08T12:34:00Z"
    assert failed_fields["error_type"] == "RuntimeError"
    assert failed_fields["error_message"] == "database unavailable"
