"""Thin application entrypoint for live ingestion worker processes."""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
from typing import Final

from fundingpulse.db import DBRuntimeConfig, db_session_factory_scope
from fundingpulse.exchange_selection import resolve_enabled_exchanges
from fundingpulse.infrastructure import http_client
from fundingpulse.ingestion.exchanges import build_live_exchange_adapters
from fundingpulse.ingestion.live.runtime import run_live_worker_loop
from fundingpulse.ingestion.logging_setup import configure_logging
from fundingpulse.ingestion.settings import build_settings
from fundingpulse.observability.logging import get_logger
from fundingpulse.tracker.exchanges import EXCHANGES

logger = get_logger(__name__)

LIVE_WORKER_HTTP_MAX_CONNECTIONS: Final = 100
LIVE_WORKER_REQUEST_CONCURRENCY: Final = 10


def build_parser() -> argparse.ArgumentParser:
    """Build the live worker CLI parser."""
    parser = argparse.ArgumentParser(description="Run a live funding ingestion worker")
    parser.add_argument(
        "--worker-id",
        help="Stable worker identity recorded on claimed live tasks",
    )
    return parser


async def run_worker(worker_id: str | None = None) -> None:
    """Bootstrap and run one live ingestion worker forever."""
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
    request_limiter = asyncio.Semaphore(LIVE_WORKER_REQUEST_CONCURRENCY)
    adapters = build_live_exchange_adapters(exchanges, request_limiter=request_limiter)
    resolved_worker_id = worker_id or _default_worker_id()

    async with db_session_factory_scope(db_config) as session_factory:
        await http_client.startup(max_connections=LIVE_WORKER_HTTP_MAX_CONNECTIONS)
        try:
            logger.info(
                "ingestion_live_worker_started",
                worker_id=resolved_worker_id,
                exchange_count=len(exchanges),
                exchanges=list(exchanges),
                adapters=sorted(adapters),
            )
            await run_live_worker_loop(
                session_factory=session_factory,
                worker_id=resolved_worker_id,
                exchange_adapters=adapters,
                config=settings.live.to_worker_config(),
            )
        finally:
            await http_client.shutdown()


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def main() -> None:
    """Main entrypoint used by CLI and process supervisors."""
    args = build_parser().parse_args()
    configure_logging(component="live-worker")
    try:
        asyncio.run(run_worker(worker_id=args.worker_id))
    except KeyboardInterrupt:
        logger.info(
            "ingestion_application_stopped",
            reason="keyboard_interrupt",
        )
    except Exception as exc:
        logger.error(
            "ingestion_application_error",
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
