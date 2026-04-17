"""Thin application entrypoint for funding tracker."""

from __future__ import annotations

import asyncio
import logging
import sys

from fundingpulse.db import DBRuntimeConfig, db_session_factory_scope
from fundingpulse.tracker.bootstrap import bootstrap
from fundingpulse.tracker.cli import build_parser
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.infrastructure import http_client
from fundingpulse.tracker.logging_setup import (
    configure_exchange_debug_logging,
    configure_live_debug_logging,
    configure_logging,
)
from fundingpulse.tracker.runtime import build_runtime_config
from fundingpulse.tracker.settings import build_settings

logger = logging.getLogger(__name__)


async def run_scheduler(
    db: DBRuntimeConfig,
    exchanges: list[str] | None,
) -> None:
    """Bootstrap and run scheduler forever."""
    async with db_session_factory_scope(db) as session_factory:
        await http_client.startup()
        try:
            scheduler = await bootstrap(
                session_factory=session_factory,
                exchanges=exchanges,
            )
            scheduler.start()
            logger.info("Scheduler started, waiting for jobs...")
            await asyncio.Event().wait()
        finally:
            await http_client.shutdown()


def main() -> None:
    """Main entrypoint used by CLI and supervisord."""
    args = build_parser().parse_args()

    try:
        settings = build_settings()
        config = build_runtime_config(args=args, settings=settings, all_exchanges=set(EXCHANGES))
    except Exception as exc:
        sys.exit(f"Configuration error: {exc}")

    configure_logging(instance_id=config.instance_id, total_instances=config.total_instances)
    configure_exchange_debug_logging(config.debug_exchanges)
    configure_live_debug_logging(config.debug_exchanges_live)

    if config.total_instances > 1:
        logger.info(
            "Instance %s/%s: running %s exchange(s): %s",
            config.instance_id,
            config.total_instances,
            len(config.exchanges or []),
            config.exchanges or [],
        )
    elif config.exchanges:
        logger.info(
            "Starting funding tracker with %s exchange(s): %s",
            len(config.exchanges),
            config.exchanges,
        )
    else:
        logger.info("Starting funding tracker with all exchanges")

    try:
        asyncio.run(
            run_scheduler(
                config.db,
                config.exchanges,
            )
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as exc:
        logger.error("Application error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
