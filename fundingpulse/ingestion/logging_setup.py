"""Logging setup shared by ingestion process entrypoints."""

from __future__ import annotations

import logging

from fundingpulse.observability.logging import configure_json_logging


def configure_logging(*, component: str) -> None:
    """Configure process-level logging for ingestion runtimes."""
    configure_json_logging(
        service="ingestion",
        component=component,
        level=logging.INFO,
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
