"""Per-exchange coordinator: scheduler-facing methods that delegate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fundingpulse.db import SessionFactory
from fundingpulse.time import utc_now
from fundingpulse.tracker.orchestration.history_sync import run_history_updates
from fundingpulse.tracker.orchestration.history_update import run_history_update
from fundingpulse.tracker.orchestration.live_collector import collect_live
from fundingpulse.tracker.orchestration.section_logger import make_section_logger

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange


class ExchangeOrchestrator:
    """Scheduler-facing facade for one exchange.

    `update()` preserves the legacy history backfill/update workflow;
    `update_history()` is the dedicated incremental history workflow;
    `update_live()` snapshots unsettled rates. All real work lives in the
    sibling modules — this class only bundles dependencies.
    """

    def __init__(
        self,
        exchange_adapter: BaseExchange,
        section_name: str,
        db: SessionFactory,
    ) -> None:
        self._adapter = exchange_adapter
        self._section_name = section_name
        self._db = db
        self._logger = make_section_logger(__name__, section_name)

    async def update(self) -> None:
        """Sync/update history for each active contract."""
        start = utc_now()
        self._logger.info("Starting update")

        stats = await run_history_updates(
            adapter=self._adapter,
            section_name=self._section_name,
            db=self._db,
            logger=self._logger,
        )
        duration = utc_now() - start
        self._logger.info(
            "History update: %d/%d contracts updated (%d new points) in %s",
            stats.contracts_updated,
            stats.contracts_total,
            stats.points_fetched,
            duration,
        )

    async def update_history(self) -> None:
        """Incrementally update settled history for each active contract."""
        await run_history_update(
            adapter=self._adapter,
            section_name=self._section_name,
            db=self._db,
        )

    async def update_live(self) -> None:
        """Collect live funding rates for all active contracts."""
        await collect_live(
            adapter=self._adapter,
            section_name=self._section_name,
            db=self._db,
        )
