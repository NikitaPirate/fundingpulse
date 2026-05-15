"""Long-running live worker runtime loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.live.config import LiveWorkerConfig
from fundingpulse.ingestion.live.constants import LIVE_FUNDING_PIPELINE
from fundingpulse.ingestion.live.dto import LiveTaskExecutionResult
from fundingpulse.ingestion.live.worker import (
    DEFAULT_LIVE_WORKER_CONFIG,
    execute_one_live_task,
)
from fundingpulse.observability.logging import EventLogger, get_logger

logger = get_logger(__name__)


class ExecuteLiveTask(Protocol):
    async def __call__(
        self,
        *,
        session_factory: SessionFactory,
        worker_id: str,
        exchange_adapters: Mapping[str, BaseLiveExchange],
        config: LiveWorkerConfig,
        event_logger: EventLogger | None = None,
    ) -> LiveTaskExecutionResult: ...


Sleep = Callable[[float], Awaitable[None]]


async def run_live_worker_loop(
    *,
    session_factory: SessionFactory,
    worker_id: str,
    exchange_adapters: Mapping[str, BaseLiveExchange],
    config: LiveWorkerConfig = DEFAULT_LIVE_WORKER_CONFIG,
    stop_event: asyncio.Event | None = None,
    event_logger: EventLogger | None = None,
    execute_task: ExecuteLiveTask = execute_one_live_task,
    sleep: Sleep = asyncio.sleep,
) -> None:
    """Poll for and execute live tasks one at a time until stopped."""
    log = event_logger or logger
    while stop_event is None or not stop_event.is_set():
        try:
            result = await execute_task(
                session_factory=session_factory,
                worker_id=worker_id,
                exchange_adapters=exchange_adapters,
                config=config,
                event_logger=log,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log_event(
                log,
                "live_worker_iteration_failed",
                worker_id=worker_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            await sleep(config.poll_interval.total_seconds())
            continue

        if not result.claimed:
            await sleep(config.poll_interval.total_seconds())


def _log_event(log: EventLogger, event: str, **fields: object) -> None:
    log.info(event, pipeline=LIVE_FUNDING_PIPELINE, **fields)
