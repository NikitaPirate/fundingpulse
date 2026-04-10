"""Logging setup helpers for funding tracker startup."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def configure_logging(instance_id: int, total_instances: int) -> None:
    """Configure base logging and optional instance tagging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if total_instances <= 1:
        return

    for handler in logging.root.handlers:
        assert handler.formatter is not None
        base_format: str = handler.formatter._fmt  # type: ignore[assignment]
        tagged_format = base_format.replace(
            "%(levelname)s", f"%(levelname)s [{instance_id}/{total_instances}]"
        )
        handler.setFormatter(logging.Formatter(tagged_format))


def configure_exchange_debug_logging(exchanges_spec: str | None) -> None:
    """Enable DEBUG logs for exchange-level loggers."""
    for exchange_name in _parse_csv(exchanges_spec):
        logging.getLogger(f"funding_tracker.exchanges.{exchange_name}").setLevel(logging.DEBUG)
    if exchanges_spec:
        logger.info("Enabling DEBUG logging for exchanges: %s", _parse_csv(exchanges_spec))


def configure_live_debug_logging(exchanges_spec: str | None) -> None:
    """Enable DEBUG logs for live collection loggers."""
    for exchange_name in _parse_csv(exchanges_spec):
        logging.getLogger(f"funding_tracker.exchanges.{exchange_name}.live").setLevel(
            logging.DEBUG
        )
    if exchanges_spec:
        logger.info("Enabling DEBUG logging for live collection: %s", _parse_csv(exchanges_spec))


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
