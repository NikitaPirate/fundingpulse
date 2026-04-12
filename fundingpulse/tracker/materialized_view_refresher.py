"""Materialized view refresher with debouncing."""

import logging
import time

from sqlalchemy import text

from fundingpulse.tracker.db import SessionFactory


class MaterializedViewRefresher:
    """Debounced refresh for materialized views."""

    def __init__(self, db: SessionFactory, debounce_seconds: int = 10) -> None:
        self._db = db
        self._debounce_seconds = debounce_seconds
        self._last_signal_time: float | None = None
        self._pending_refresh = False
        self._logger = logging.getLogger(__name__)

    def signal_contracts_changed(self, exchange_name: str) -> None:
        self._last_signal_time = time.time()
        self._pending_refresh = True
        self._logger.debug(f"Received contracts change signal from {exchange_name}")

    async def check_and_refresh_if_needed(self) -> None:
        """Executes refresh if debounce period elapsed; retries on failure."""
        if not self._pending_refresh or self._last_signal_time is None:
            return

        time_since_last_signal = time.time() - self._last_signal_time

        if time_since_last_signal >= self._debounce_seconds:
            try:
                await self._refresh_materialized_views()
                self._pending_refresh = False
                self._last_signal_time = None
                self._logger.info("Materialized views refresh completed")
            except Exception as e:
                # NOTE: no error raising - this is optimisation, not critical functionality.
                self._logger.error(
                    f"Failed to refresh materialized views: {e}",
                    exc_info=True,
                )
        else:
            remaining_time = self._debounce_seconds - time_since_last_signal
            self._logger.debug(f"Waiting {remaining_time:.1f}s more before refresh")

    async def _refresh_materialized_views(self) -> None:
        async with self._db.begin() as session:
            self._logger.debug("Starting materialized views refresh")
            await session.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY contract_enriched;")
            )
