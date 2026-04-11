"""Scheduler bootstrap for funding tracker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from fundingpulse.tracker.db import SessionFactory, setup_db_session
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.materialized_view_refresher import MaterializedViewRefresher
from fundingpulse.tracker.orchestration import ExchangeOrchestrator

logger = logging.getLogger(__name__)


async def bootstrap(
    db_connection: str,
    db_engine_kwargs: dict[str, Any],
    db_session_kwargs: dict[str, Any],
    exchanges: list[str] | None = None,
    concurrency_limit: int = 10,
    mv_refresher_debounce: int = 10,
) -> AsyncIOScheduler:
    """Build and return configured scheduler."""
    resolved_exchanges = _resolve_exchanges(exchanges)
    session_factory = setup_db_session(
        db_connection,
        session_kwargs=db_session_kwargs,
        engine_kwargs=db_engine_kwargs,
    )
    mv_refresher = MaterializedViewRefresher(
        session_factory=session_factory,
        debounce_seconds=mv_refresher_debounce,
    )
    scheduler = _create_scheduler()

    _register_exchange_jobs(
        scheduler=scheduler,
        exchange_names=resolved_exchanges,
        session_factory=session_factory,
        mv_refresher=mv_refresher,
        concurrency_limit=concurrency_limit,
    )
    _register_service_jobs(scheduler=scheduler, mv_refresher=mv_refresher)

    logger.info(
        "Bootstrap complete: %s exchange(s), %s job(s)",
        len(resolved_exchanges),
        len(scheduler.get_jobs()),
    )
    return scheduler


def _resolve_exchanges(exchanges: list[str] | None) -> list[str]:
    """Resolve exchange selection and validate unknown IDs."""
    if exchanges is None:
        selected = sorted(EXCHANGES.keys())
        logger.info("No exchanges specified, using all registered: %s", selected)
        return selected
    if not exchanges:
        logger.info("No exchanges assigned to this instance")
        return []

    available = set(EXCHANGES.keys())
    unknown = [exchange for exchange in exchanges if exchange not in available]
    if unknown:
        logger.warning(
            "Unknown exchange IDs will be skipped: %s. Available: %s",
            sorted(set(unknown)),
            sorted(available),
        )

    valid = [exchange for exchange in exchanges if exchange in available]
    if not valid:
        raise KeyError(f"No valid exchanges left after filtering: {sorted(set(unknown))}")

    logger.info("Bootstrapping funding tracker for exchanges: %s", valid)
    return valid


def _create_scheduler() -> AsyncIOScheduler:
    """Create scheduler with default behavior."""
    return AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        }
    )


def _register_exchange_jobs(
    scheduler: AsyncIOScheduler,
    exchange_names: list[str],
    session_factory: SessionFactory,
    mv_refresher: MaterializedViewRefresher,
    concurrency_limit: int,
) -> None:
    """Register update and live jobs for each exchange."""
    if not exchange_names:
        logger.info("No exchange jobs to register")
        return

    seconds_per_exchange = 60 // len(exchange_names)

    for index, exchange_name in enumerate(exchange_names):
        orchestrator = ExchangeOrchestrator(
            exchange_adapter=EXCHANGES[exchange_name],
            section_name=exchange_name,
            session_factory=session_factory,
            semaphore=asyncio.Semaphore(concurrency_limit),
            mv_refresher=mv_refresher,
        )
        _register_update_job(scheduler, exchange_name, orchestrator)

        second = index * seconds_per_exchange
        _register_live_job(scheduler, exchange_name, second, orchestrator)


def _register_update_job(
    scheduler: AsyncIOScheduler,
    exchange_name: str,
    orchestrator: ExchangeOrchestrator,
) -> None:
    scheduler.add_job(
        orchestrator.update,
        trigger=OrTrigger(
            [
                DateTrigger(),
                CronTrigger(hour="*", minute=0, second=5),
            ]
        ),
        name=f"{exchange_name}_update",
    )
    logger.info("Registered update job for %s (immediate + hourly)", exchange_name)


def _register_live_job(
    scheduler: AsyncIOScheduler,
    exchange_name: str,
    second: int,
    orchestrator: ExchangeOrchestrator,
) -> None:
    scheduler.add_job(
        orchestrator.update_live,
        trigger=CronTrigger(second=second),
        name=f"{exchange_name}_live",
    )
    logger.info(
        "Registered live rate collection for %s (every minute at :%02d)",
        exchange_name,
        second,
    )


def _register_service_jobs(
    scheduler: AsyncIOScheduler, mv_refresher: MaterializedViewRefresher
) -> None:
    """Register process-wide background jobs."""
    scheduler.add_job(
        mv_refresher.check_and_refresh_if_needed,
        trigger=CronTrigger(second="*"),
        name="materialized_views_refresher",
    )
    logger.info("Registered materialized view refresher (every second)")
