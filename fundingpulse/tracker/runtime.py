"""Runtime configuration building for funding tracker startup."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Any

from fundingpulse.tracker.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeConfig:
    """Resolved startup configuration after CLI/ENV merge."""

    db_connection: str
    db_engine_kwargs: dict[str, Any]
    db_session_kwargs: dict[str, Any]
    exchanges: list[str] | None
    debug_exchanges: str | None
    debug_exchanges_live: str | None
    instance_id: int
    total_instances: int


def build_runtime_config(
    args: argparse.Namespace, settings: Settings, all_exchanges: set[str]
) -> RuntimeConfig:
    """Resolve final runtime configuration used by main()."""
    exchanges_arg = args.exchanges if args.exchanges is not None else settings.exchanges
    debug_exchanges_arg = (
        args.debug_exchanges if args.debug_exchanges is not None else settings.debug_exchanges
    )
    debug_exchanges_live_arg = (
        args.debug_exchanges_live
        if args.debug_exchanges_live is not None
        else settings.debug_exchanges_live
    )
    instance_id = args.instance_id if args.instance_id is not None else settings.instance_id
    total_instances = (
        args.total_instances if args.total_instances is not None else settings.total_instances
    )

    if total_instances <= 0:
        raise ValueError("TOTAL_INSTANCES must be greater than 0")
    if instance_id < 0:
        raise ValueError("INSTANCE_ID must be >= 0")
    if instance_id >= total_instances:
        raise ValueError("INSTANCE_ID must be less than TOTAL_INSTANCES")

    exchanges = _parse_exchanges_spec(exchanges_arg, all_exchanges)

    if exchanges is None:
        exchanges = sorted(all_exchanges)

    if total_instances > 1:
        exchanges = _filter_exchanges_by_instance(exchanges, instance_id, total_instances)
    elif len(exchanges) == len(all_exchanges):
        exchanges = None

    return RuntimeConfig(
        db_connection=settings.db_connection,
        db_engine_kwargs=_resolve_engine_kwargs(settings.db.engine_kwargs),
        db_session_kwargs=_resolve_session_kwargs(settings.db.session_kwargs),
        exchanges=exchanges,
        debug_exchanges=debug_exchanges_arg,
        debug_exchanges_live=debug_exchanges_live_arg,
        instance_id=instance_id,
        total_instances=total_instances,
    )


def _parse_exchanges_spec(exchanges_spec: str | None, all_exchanges: set[str]) -> list[str] | None:
    """Parse and validate comma-separated exchanges string."""
    if not exchanges_spec:
        return None

    requested = {item.strip() for item in exchanges_spec.split(",") if item.strip()}
    if not requested:
        return None

    unknown = requested - all_exchanges
    if unknown:
        logger.warning(
            "Unknown exchange IDs requested: %s. Available exchanges: %s",
            sorted(unknown),
            sorted(all_exchanges),
        )

    valid = sorted(requested & all_exchanges)
    if valid:
        logger.info("Filtered to %s exchange(s): %s", len(valid), valid)
        return valid

    return None


def _resolve_engine_kwargs(service_engine_kwargs: dict[str, Any] | None) -> dict[str, Any]:
    defaults = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": 30,
        "max_overflow": 200,
    }
    return {**defaults, **(service_engine_kwargs or {})}


def _resolve_session_kwargs(service_session_kwargs: dict[str, Any] | None) -> dict[str, Any]:
    defaults = {
        "expire_on_commit": False,
    }
    return {**defaults, **(service_session_kwargs or {})}


def _filter_exchanges_by_instance(
    exchanges: list[str], instance_id: int, total_instances: int
) -> list[str]:
    """Distribute exchanges across instances by simple round-robin."""
    if total_instances <= 1:
        return exchanges

    sorted_exchanges = sorted(exchanges)
    return sorted_exchanges[instance_id::total_instances]
