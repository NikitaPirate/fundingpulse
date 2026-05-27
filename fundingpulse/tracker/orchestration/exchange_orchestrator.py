"""Per-exchange coordinator: scheduler-facing methods that delegate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fundingpulse.db import SessionFactory
from fundingpulse.tracker.orchestration.history_backfill import run_history_backfill
from fundingpulse.tracker.orchestration.history_update import run_history_update
from fundingpulse.tracker.orchestration.live_collector import collect_live

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange


class ExchangeOrchestrator:
    """Scheduler-facing facade for one exchange.

    Backfill, incremental history, and live collection are separate workflows.
    All real work lives in sibling modules — this class only bundles scheduler
    dependencies.
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

    async def backfill_history(self) -> None:
        """Backfill older settled history for unsynced contracts."""
        await run_history_backfill(
            adapter=self._adapter,
            section_name=self._section_name,
            db=self._db,
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
