"""Runtime configuration building for funding tracker startup."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from fundingpulse.db import DBRuntimeConfig
from fundingpulse.exchange_selection import (
    parse_exchange_ids,
    resolve_enabled_exchanges,
)
from fundingpulse.tracker.settings import Settings


@dataclass(frozen=True)
class RuntimeConfig:
    """Resolved startup configuration after CLI/ENV merge."""

    db: DBRuntimeConfig
    exchanges: list[str] | None
    registry_exchanges: list[str]
    owns_singleton_jobs: bool
    debug_exchanges: str | None
    debug_exchanges_live: str | None
    instance_id: int
    total_instances: int


def build_runtime_config(
    args: argparse.Namespace, settings: Settings, all_exchanges: set[str]
) -> RuntimeConfig:
    """Resolve final runtime configuration used by main()."""
    app = settings.app
    exchanges_source = "--exchanges" if args.exchanges is not None else "ENABLED_EXCHANGES"
    exchanges_arg = (
        parse_exchange_ids(args.exchanges)
        if args.exchanges is not None
        else settings.exchange_selection.enabled_exchanges
    )
    debug_exchanges_arg = (
        args.debug_exchanges if args.debug_exchanges is not None else app.debug_exchanges
    )
    debug_exchanges_live_arg = (
        args.debug_exchanges_live
        if args.debug_exchanges_live is not None
        else app.debug_exchanges_live
    )
    instance_id = args.instance_id if args.instance_id is not None else app.instance_id
    total_instances = (
        args.total_instances if args.total_instances is not None else app.total_instances
    )

    if total_instances <= 0:
        raise ValueError("FT_TOTAL_INSTANCES must be greater than 0")
    if instance_id < 0:
        raise ValueError("FT_INSTANCE_ID must be >= 0")
    if instance_id >= total_instances:
        raise ValueError("FT_INSTANCE_ID must be less than FT_TOTAL_INSTANCES")

    selected_exchanges = resolve_enabled_exchanges(
        exchanges_arg,
        all_exchanges,
        source=exchanges_source,
    )
    registry_exchanges = selected_exchanges if instance_id == 0 else []
    owns_singleton_jobs = instance_id == 0

    exchanges: list[str] | None = selected_exchanges
    if total_instances > 1:
        exchanges = _filter_exchanges_by_instance(exchanges, instance_id, total_instances)
    elif len(exchanges) == len(all_exchanges):
        exchanges = None

    return RuntimeConfig(
        db=DBRuntimeConfig(
            connection_url=settings.db.connection_url,
            engine_kwargs=settings.db_tuning.engine_kwargs,
            session_kwargs=settings.db_tuning.session_kwargs,
        ),
        exchanges=exchanges,
        registry_exchanges=registry_exchanges,
        owns_singleton_jobs=owns_singleton_jobs,
        debug_exchanges=debug_exchanges_arg,
        debug_exchanges_live=debug_exchanges_live_arg,
        instance_id=instance_id,
        total_instances=total_instances,
    )


def _filter_exchanges_by_instance(
    exchanges: list[str], instance_id: int, total_instances: int
) -> list[str]:
    """Distribute exchanges across instances by simple round-robin."""
    if total_instances <= 1:
        return exchanges

    sorted_exchanges = sorted(exchanges)
    return sorted_exchanges[instance_id::total_instances]
