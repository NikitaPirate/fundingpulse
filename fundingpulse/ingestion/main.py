"""Thin application entrypoint for ingestion scheduler processes."""

from __future__ import annotations

import asyncio
import logging
import sys

from fundingpulse.db import DBRuntimeConfig, db_session_factory_scope
from fundingpulse.exchange_selection import resolve_enabled_exchanges
from fundingpulse.ingestion.exchanges import LIVE_EXCHANGES
from fundingpulse.ingestion.scheduler import bootstrap_scheduler
from fundingpulse.ingestion.settings import build_settings

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
        LIVE_EXCHANGES.keys(),
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


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    """Main entrypoint used by CLI and process supervisors."""
    _configure_logging()
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as exc:
        logger.error("Application error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
