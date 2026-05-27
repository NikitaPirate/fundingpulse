"""Scheduler bootstrap for funding tracker."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from fundingpulse.db import SessionFactory
from fundingpulse.models.section import Section
from fundingpulse.time import UTC, utc_now
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.materialized_view_refresher import MaterializedViewRefresher
from fundingpulse.tracker.orchestration import ExchangeOrchestrator
from fundingpulse.tracker.orchestration.contract_registry import run_contract_registry
from fundingpulse.tracker.queries.utils import bulk_insert
from fundingpulse.tracker.services.asset_ranking import update_rankings

logger = logging.getLogger(__name__)


async def bootstrap(
    session_factory: SessionFactory,
    exchanges: list[str] | None = None,
    registry_exchanges: list[str] | None = None,
    owns_singleton_jobs: bool = True,
    concurrency_limit: int = 10,
    mv_refresher_debounce: int = 10,
) -> AsyncIOScheduler:
    """Build and return configured scheduler."""
    resolved_exchanges = _resolve_exchanges(exchanges)
    requested_registry_exchanges = _resolve_exchanges(registry_exchanges or [])
    resolved_registry_exchanges = requested_registry_exchanges if owns_singleton_jobs else []
    if requested_registry_exchanges and not owns_singleton_jobs:
        logger.info("Skipping contract registry jobs on non-owner instance")
    await _ensure_sections(
        session_factory,
        sorted({*resolved_exchanges, *resolved_registry_exchanges}),
    )
    mv_refresher = MaterializedViewRefresher(
        db=session_factory,
        debounce_seconds=mv_refresher_debounce,
    )
    scheduler = _create_scheduler()

    _register_exchange_jobs(
        scheduler=scheduler,
        exchange_names=resolved_exchanges,
        session_factory=session_factory,
        concurrency_limit=concurrency_limit,
    )
    _register_contract_registry_jobs(
        scheduler=scheduler,
        exchange_names=resolved_registry_exchanges,
        session_factory=session_factory,
        mv_refresher=mv_refresher,
        concurrency_limit=concurrency_limit,
    )
    if owns_singleton_jobs:
        _register_service_jobs(
            scheduler=scheduler,
            mv_refresher=mv_refresher,
            session_factory=session_factory,
        )
    else:
        logger.info("Skipping singleton service jobs on this instance")

    logger.info(
        "Bootstrap complete: %s collection exchange(s), %s registry exchange(s), %s job(s)",
        len(resolved_exchanges),
        len(resolved_registry_exchanges),
        len(scheduler.get_jobs()),
    )
    return scheduler


async def _ensure_sections(session_factory: SessionFactory, exchange_names: list[str]) -> None:
    """Seed the `section` table for every exchange this instance handles.

    Sections are static — one row per exchange — and only need to exist before
    contracts reference them. Doing this once at bootstrap keeps the hourly
    registration cycle free of the upsert.
    """
    if not exchange_names:
        return
    rows = [Section(name=name) for name in exchange_names]
    async with session_factory.begin() as session:
        await bulk_insert(session, Section, rows, on_conflict="ignore")


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
        timezone=UTC,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )


def _register_exchange_jobs(
    scheduler: AsyncIOScheduler,
    exchange_names: list[str],
    session_factory: SessionFactory,
    concurrency_limit: int,
) -> None:
    """Register history backfill, history update, and live jobs for each exchange."""
    if not exchange_names:
        logger.info("No exchange jobs to register")
        return

    seconds_per_exchange = 60 // len(exchange_names)

    for index, exchange_name in enumerate(exchange_names):
        adapter = EXCHANGES[exchange_name](
            semaphore=asyncio.Semaphore(concurrency_limit),
        )

        orchestrator = ExchangeOrchestrator(
            exchange_adapter=adapter,
            section_name=exchange_name,
            db=session_factory,
        )
        _register_history_backfill_job(scheduler, exchange_name, orchestrator)
        _register_history_update_job(scheduler, exchange_name, orchestrator)
        second = index * seconds_per_exchange
        _register_live_job(scheduler, exchange_name, second, orchestrator)


def _register_history_update_job(
    scheduler: AsyncIOScheduler,
    exchange_name: str,
    orchestrator: ExchangeOrchestrator,
) -> None:
    scheduler.add_job(
        orchestrator.update_history,
        trigger=OrTrigger(
            [
                DateTrigger(run_date=utc_now(), timezone=UTC),
                CronTrigger(hour="*", minute=0, second=5, timezone=UTC),
            ]
        ),
        name=f"{exchange_name}_history_update",
    )
    logger.info(
        "Registered history update job for %s (immediate + hourly at :00:05)",
        exchange_name,
    )


def _register_history_backfill_job(
    scheduler: AsyncIOScheduler,
    exchange_name: str,
    orchestrator: ExchangeOrchestrator,
) -> None:
    delayed_start = utc_now() + timedelta(minutes=5)
    scheduler.add_job(
        orchestrator.backfill_history,
        trigger=OrTrigger(
            [
                DateTrigger(run_date=delayed_start, timezone=UTC),
                CronTrigger(
                    hour="*",
                    minute=5,
                    second=0,
                    start_date=delayed_start,
                    timezone=UTC,
                ),
            ]
        ),
        name=f"{exchange_name}_history_backfill",
    )
    logger.info(
        "Registered history backfill job for %s (startup +5m + hourly at :05:00)",
        exchange_name,
    )


def _register_live_job(
    scheduler: AsyncIOScheduler,
    exchange_name: str,
    second: int,
    orchestrator: ExchangeOrchestrator,
) -> None:
    scheduler.add_job(
        orchestrator.update_live,
        trigger=CronTrigger(second=second, timezone=UTC),
        name=f"{exchange_name}_live",
    )
    logger.info(
        "Registered live rate collection for %s (every minute at :%02d)",
        exchange_name,
        second,
    )


def _register_contract_registry_jobs(
    scheduler: AsyncIOScheduler,
    exchange_names: list[str],
    session_factory: SessionFactory,
    mv_refresher: MaterializedViewRefresher,
    concurrency_limit: int,
) -> None:
    """Register contract registry jobs for singleton maintenance ownership."""
    if not exchange_names:
        logger.info("No contract registry jobs to register")
        return

    for exchange_name in exchange_names:
        adapter = EXCHANGES[exchange_name](
            semaphore=asyncio.Semaphore(concurrency_limit),
        )
        scheduler.add_job(
            run_contract_registry,
            kwargs={
                "adapter": adapter,
                "section_name": exchange_name,
                "db": session_factory,
                "mv_refresher": mv_refresher,
            },
            trigger=OrTrigger(
                [
                    DateTrigger(run_date=utc_now(), timezone=UTC),
                    CronTrigger(minute="4-59/5", second=0, timezone=UTC),
                ]
            ),
            name=f"{exchange_name}_contract_registry",
        )
        logger.info(
            "Registered contract registry for %s (immediate + every 5 minutes starting at :04)",
            exchange_name,
        )


def _register_service_jobs(
    scheduler: AsyncIOScheduler,
    mv_refresher: MaterializedViewRefresher,
    session_factory: SessionFactory,
) -> None:
    """Register process-wide background jobs."""
    scheduler.add_job(
        mv_refresher.check_and_refresh_if_needed,
        trigger=CronTrigger(second="*", timezone=UTC),
        name="materialized_views_refresher",
    )
    logger.info("Registered materialized view refresher (every second)")

    scheduler.add_job(
        update_rankings,
        args=[session_factory],
        trigger=OrTrigger(
            [
                DateTrigger(run_date=utc_now(), timezone=UTC),
                CronTrigger(hour=14, minute=30, timezone=UTC),
            ]
        ),
        name="asset_ranking_update",
    )
    logger.info("Registered asset ranking update (immediate + daily 14:30 UTC)")
