"""Live funding task scheduling use-case."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Final

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.ingestion.live.constants import (
    LIVE_FUNDING_PIPELINE,
    LIVE_FUNDING_TASK_KEY_PREFIX,
)
from fundingpulse.ingestion.live.dto import LiveEnqueueResult, LiveEnqueueTick
from fundingpulse.ingestion.live.queries import (
    get_active_live_task_exchanges,
    insert_pending_live_task,
    mark_stale_running_live_tasks_failed,
)
from fundingpulse.observability.logging import EventLogger, get_logger
from fundingpulse.time import UtcDateTime, to_iso8601, utc_now

DEFAULT_LIVE_ENQUEUER_CONFIG: Final = LiveEnqueuerConfig()

logger = get_logger(__name__)


async def enqueue_live_funding_tick(
    *,
    session_factory: SessionFactory,
    exchanges: Sequence[str],
    now: UtcDateTime | None = None,
    config: LiveEnqueuerConfig = DEFAULT_LIVE_ENQUEUER_CONFIG,
    event_logger: EventLogger | None = None,
) -> LiveEnqueueResult:
    """Schedule live funding snapshot tasks for one UTC minute bucket."""
    log = event_logger or logger
    tick = LiveEnqueueTick.from_instant(now or utc_now(), config)

    log.info(
        "live_enqueue_started",
        pipeline=LIVE_FUNDING_PIPELINE,
        scheduled_for=to_iso8601(tick.scheduled_for),
    )

    try:
        async with asyncio.timeout(config.enqueue_timeout.total_seconds()):
            return await _enqueue_live_funding_tick(
                session_factory=session_factory,
                exchanges=list(exchanges),
                tick=tick,
                log=log,
            )
    except Exception as exc:
        log.info(
            "live_enqueue_failed",
            pipeline=LIVE_FUNDING_PIPELINE,
            scheduled_for=to_iso8601(tick.scheduled_for),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise


async def _enqueue_live_funding_tick(
    *,
    session_factory: SessionFactory,
    exchanges: list[str],
    tick: LiveEnqueueTick,
    log: EventLogger,
) -> LiveEnqueueResult:
    async with session_factory.begin() as session:
        stale_tasks = await mark_stale_running_live_tasks_failed(
            session=session,
            tick=tick,
        )
        active_exchanges = await get_active_live_task_exchanges(session, exchanges)

        created_tasks = 0
        duplicate_tasks = 0
        skipped_active_tasks = 0
        for exchange in exchanges:
            task_key = build_live_funding_task_key(exchange, tick.scheduled_for)
            if exchange in active_exchanges:
                skipped_active_tasks += 1
                _log_task_skipped(
                    log,
                    task_key=task_key,
                    exchange=exchange,
                    scheduled_for=tick.scheduled_for,
                    reason="active_work",
                )
                continue

            created = await insert_pending_live_task(
                session=session,
                task_key=task_key,
                exchange=exchange,
                scheduled_for=tick.scheduled_for,
            )
            if created:
                created_tasks += 1
                log.info(
                    "live_task_created",
                    pipeline=LIVE_FUNDING_PIPELINE,
                    task_key=task_key,
                    exchange=exchange,
                    scheduled_for=to_iso8601(tick.scheduled_for),
                )
            else:
                duplicate_tasks += 1
                _log_task_skipped(
                    log,
                    task_key=task_key,
                    exchange=exchange,
                    scheduled_for=tick.scheduled_for,
                    reason="duplicate_task",
                )

    result = LiveEnqueueResult(
        scheduled_for=tick.scheduled_for,
        selected_exchanges=len(exchanges),
        created_tasks=created_tasks,
        skipped_active_tasks=skipped_active_tasks,
        duplicate_tasks=duplicate_tasks,
        stale_failed_tasks=len(stale_tasks),
    )
    log.info(
        "live_enqueue_completed",
        pipeline=LIVE_FUNDING_PIPELINE,
        scheduled_for=to_iso8601(tick.scheduled_for),
        selected_exchanges=result.selected_exchanges,
        created_tasks=result.created_tasks,
        skipped_active_tasks=result.skipped_active_tasks,
        duplicate_tasks=result.duplicate_tasks,
        stale_failed_tasks=result.stale_failed_tasks,
        stale_before=to_iso8601(tick.stale_before),
    )
    return result


def build_live_funding_task_key(exchange: str, scheduled_for: UtcDateTime) -> str:
    """Build the stable idempotency key for one exchange-level live snapshot task."""
    return f"{LIVE_FUNDING_TASK_KEY_PREFIX}:{exchange}:{to_iso8601(scheduled_for)}"


def _log_task_skipped(
    log: EventLogger,
    *,
    task_key: str,
    exchange: str,
    scheduled_for: UtcDateTime,
    reason: str,
) -> None:
    log.info(
        "live_task_skipped",
        pipeline=LIVE_FUNDING_PIPELINE,
        task_key=task_key,
        exchange=exchange,
        scheduled_for=to_iso8601(scheduled_for),
        reason=reason,
    )
