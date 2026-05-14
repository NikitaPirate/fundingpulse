"""APScheduler wiring for ingestion jobs."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.config import LiveEnqueuerConfig
from fundingpulse.ingestion.live.enqueuer import enqueue_live_funding_tick
from fundingpulse.time import UTC

logger = logging.getLogger(__name__)


def bootstrap_scheduler(
    *,
    session_factory: SessionFactory,
    exchanges: Sequence[str],
    live_config: LiveEnqueuerConfig,
) -> AsyncIOScheduler:
    """Build the ingestion scheduler without starting it."""
    scheduler = AsyncIOScheduler(
        timezone=UTC,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 60,
        },
    )
    _register_live_enqueuer(
        scheduler=scheduler,
        session_factory=session_factory,
        exchanges=exchanges,
        live_config=live_config,
    )
    logger.info(
        "Ingestion scheduler bootstrap complete: %s exchange(s), %s job(s)",
        len(exchanges),
        len(scheduler.get_jobs()),
    )
    return scheduler


def _register_live_enqueuer(
    *,
    scheduler: AsyncIOScheduler,
    session_factory: SessionFactory,
    exchanges: Sequence[str],
    live_config: LiveEnqueuerConfig,
) -> None:
    scheduler.add_job(
        enqueue_live_funding_tick,
        kwargs={
            "session_factory": session_factory,
            "exchanges": list(exchanges),
            "config": live_config,
        },
        trigger=CronTrigger(second=0, timezone=UTC),
        id="live_funding_enqueue",
        name="live_funding_enqueue",
        replace_existing=True,
    )
