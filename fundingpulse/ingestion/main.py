"""Thin application entrypoint for ingestion scheduler processes."""

from __future__ import annotations

import asyncio
import logging
import sys

from fundingpulse.db import DBRuntimeConfig, db_session_factory_scope
from fundingpulse.exchange_selection import resolve_enabled_exchanges
from fundingpulse.ingestion.logging_setup import configure_logging
from fundingpulse.ingestion.scheduler import bootstrap_scheduler
from fundingpulse.ingestion.settings import build_settings
from fundingpulse.tracker.exchanges import EXCHANGES

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Bootstrap and run the ingestion scheduler forever."""
    settings = build_settings()
    db_config = DBRuntimeConfig(
        connection_url=settings.db.connection_url,
        engine_kwargs=settings.db_tuning.engine_kwargs,
        session_kwargs=settings.db_tuning.session_kwargs,
    )
    exchanges = resolve_enabled_exchanges(
        settings.exchange_selection.enabled_exchanges,
        EXCHANGES.keys(),
        source="ENABLED_EXCHANGES",
    )

    async with db_session_factory_scope(db_config) as session_factory:
        scheduler = bootstrap_scheduler(
            session_factory=session_factory,
            exchanges=exchanges,
            live_config=settings.live.to_enqueuer_config(),
        )
        scheduler.start()
        logger.info("Ingestion scheduler started")
        try:
            await asyncio.Event().wait()
        finally:
            scheduler.shutdown(wait=False)


def main() -> None:
    """Main entrypoint used by CLI and process supervisors."""
    configure_logging()
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as exc:
        logger.error("Application error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
