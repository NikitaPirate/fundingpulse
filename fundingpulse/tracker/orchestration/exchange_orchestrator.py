"""Exchange orchestrator — coordinates data collection for a single exchange."""

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.models.quote import Quote
from fundingpulse.models.section import Section
from fundingpulse.tracker.db import SessionFactory
from fundingpulse.tracker.db.contracts import get_active_by_section, get_by_section, upsert_many
from fundingpulse.tracker.db.funding_points import get_newest_for_contract, get_oldest_for_contract
from fundingpulse.tracker.db.utils import bulk_insert
from fundingpulse.tracker.materialized_view_refresher import MaterializedViewRefresher

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)

# Log progress every N batches during sync operations
PROGRESS_LOG_BATCH_INTERVAL = 10


class ExchangeOrchestrator:
    """Coordinates data collection for a single exchange.

    Provides two entry points:
    - update() — register contracts, then sync/update historical funding data
    - update_live() — collect current unsettled funding rates
    """

    def __init__(
        self,
        exchange_adapter: BaseExchange,
        section_name: str,
        db: SessionFactory,
        semaphore: asyncio.Semaphore,
        mv_refresher: MaterializedViewRefresher,
    ) -> None:
        self._exchange_adapter = exchange_adapter
        self._section_name = section_name
        self._db = db
        self._mv_refresher = mv_refresher
        self._semaphore = semaphore

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def update(self) -> None:
        """Register contracts, then sync/update history for each."""
        start_time = datetime.now()
        logger.info(f"Starting update for {self._section_name}")

        try:
            await self._register_contracts()
        except Exception as e:
            logger.error(
                f"Failed to register contracts for {self._section_name}: {e}",
                exc_info=True,
            )
            return

        async with self._db.begin() as session:
            contracts = await get_active_by_section(session, self._section_name)

        if not contracts:
            logger.warning(f"No contracts found for {self._section_name}")
            duration = datetime.now() - start_time
            logger.info(
                f"Update completed for {self._section_name} in {duration} "
                f"(no contracts to process)"
            )
            return

        logger.debug(f"Processing {len(contracts)} contracts for {self._section_name}")
        results = await self._process_all_contracts(contracts)
        self._log_update_stats(contracts, results, start_time)

    async def update_live(self) -> None:
        """Collect live funding rates for all active contracts."""
        logger.debug(f"Collecting live rates for {self._section_name}")

        try:
            async with self._db.begin() as session:
                contracts = await get_active_by_section(session, self._section_name)

            if not contracts:
                logger.warning(f"[{self._section_name}] No active contracts for live collection")
                return

            logger.debug(
                f"[{self._section_name}] Collecting live rates for {len(contracts)} contracts"
            )

            rates_by_contract = await self._exchange_adapter.fetch_live(list(contracts))

            if not rates_by_contract:
                logger.warning(f"[{self._section_name}] No live rates collected")
                return

            live_records = [
                LiveFundingPoint(
                    contract_id=contract.id,
                    timestamp=rate.timestamp,
                    funding_rate=rate.rate,
                )
                for contract, rate in rates_by_contract.items()
            ]

            async with self._db.begin() as session:
                await bulk_insert(session, LiveFundingPoint, live_records, on_conflict="ignore")

            success_count = len(live_records)
            failure_count = len(contracts) - success_count

            if failure_count > 0:
                logger.info(
                    f"[{self._section_name}] Live rate collection: "
                    f"{success_count} success, {failure_count} failed"
                )
            else:
                logger.debug(
                    f"[{self._section_name}] Live rate collection: "
                    f"all {success_count} rates collected successfully"
                )
        except Exception as e:
            logger.error(
                f"Failed to collect live rates for {self._section_name}: {e}",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Private: contract registration
    # ------------------------------------------------------------------

    async def _register_contracts(self) -> None:
        """Sync contract list from exchange API to database.

        Marks contracts missing from API as deprecated, upserts active ones,
        and signals the materialized view refresher on changes.
        """
        logger.debug(f"[{self._section_name}] Starting contract sync")

        api_contracts = await self._exchange_adapter.get_contracts()
        logger.debug(f"[{self._section_name}] Fetched {len(api_contracts)} contracts from API")

        if not api_contracts:
            logger.warning(f"[{self._section_name}] No contracts returned from API")
            return

        async with self._db.begin() as session:
            await bulk_insert(
                session, Section, [Section(name=self._section_name)], on_conflict="ignore"
            )

            quotes = {Quote(name=contract.quote) for contract in api_contracts}
            await bulk_insert(session, Quote, quotes, on_conflict="ignore")
            logger.debug(f"[{self._section_name}] Inserted {len(quotes)} unique quotes")

            assets = {Asset(name=contract.asset_name) for contract in api_contracts}
            await bulk_insert(session, Asset, assets, on_conflict="ignore")
            logger.debug(f"[{self._section_name}] Inserted {len(assets)} unique assets")

            existing_contracts = await get_by_section(session, self._section_name)
            logger.debug(
                f"[{self._section_name}] Found {len(existing_contracts)} existing contracts in DB"
            )

            api_contract_keys = {(c.asset_name, c.quote) for c in api_contracts}

            deprecated_count = 0
            for contract in existing_contracts:
                if (contract.asset_name, contract.quote_name) not in api_contract_keys:
                    contract.deprecated = True
                    deprecated_count += 1

            if deprecated_count > 0:
                logger.debug(
                    f"[{self._section_name}] Marked {deprecated_count} contracts as deprecated"
                )

            contracts_to_upsert = [
                Contract(
                    asset_name=c.asset_name,
                    quote_name=c.quote,
                    section_name=self._section_name,
                    funding_interval=c.funding_interval,
                    deprecated=False,
                )
                for c in api_contracts
            ]

            await upsert_many(session, contracts_to_upsert)

            logger.info(
                f"[{self._section_name}] Contract sync completed: "
                f"{len(api_contracts)} active, {deprecated_count} deprecated"
            )

        await self._mv_refresher.signal_contracts_changed(self._section_name)
        logger.debug(f"[{self._section_name}] Signaled MV refresher")

    # ------------------------------------------------------------------
    # Private: history processing
    # ------------------------------------------------------------------

    async def _process_all_contracts(self, contracts: Sequence[Contract]) -> list[tuple[int, int]]:
        """Process all contracts concurrently with semaphore control."""
        logger.debug(f"[{self._section_name}] Starting gather for {len(contracts)} contracts")
        tasks = [self._process_contract(contract) for contract in contracts]
        results = await asyncio.gather(*tasks)
        logger.debug(f"[{self._section_name}] Gather complete")
        return list(results)

    async def _process_contract(self, contract: Contract) -> tuple[int, int]:
        """Process a single contract with timeout and error isolation.

        Returns:
            (was_updated, points): 1/0 flag and number of new data points.
        """
        async with self._semaphore:
            try:
                if not contract.synced:
                    async with asyncio.timeout(600.0):
                        points = await self._sync_contract(contract)
                else:
                    async with asyncio.timeout(60.0):
                        points = await self._update_contract(contract)
                return (1 if points > 0 else 0, points)
            except TimeoutError:
                contract_id = f"{contract.asset.name}/{contract.quote_name}"
                timeout_duration = "10m" if not contract.synced else "1m"
                logger.warning(
                    f"[{self._section_name}] {contract_id} timed out after "
                    f"{timeout_duration} — operation: "
                    f"{'sync' if not contract.synced else 'update'}"
                )
                return (0, 0)
            except Exception as e:
                logger.error(
                    f"[{self._section_name}] Failed to process contract "
                    f"{contract.asset.name}/{contract.quote_name}: {e}",
                    exc_info=True,
                )
                return (0, 0)

    async def _sync_contract(self, contract: Contract) -> int:
        """Fetch full history backwards until no more data; mark contract as synced.

        Opens/closes sessions per DB operation to avoid holding connections
        during long API calls.
        """
        if contract.synced:
            logger.debug(
                f"[{self._section_name}] {contract.asset.name}/{contract.quote_name} "
                f"already synced, skipping"
            )
            return 0

        logger.debug(
            f"[{self._section_name}] Starting sync for {contract.asset.name}/{contract.quote_name}"
        )

        total_points = 0
        batch_count = 0

        while True:
            batch_count += 1

            async with self._db.begin() as session:
                oldest = await get_oldest_for_contract(session, contract.id)
                before_timestamp = oldest.timestamp - timedelta(seconds=1) if oldest else None

            logger.debug(
                f"[{self._section_name}] Sync batch #{batch_count}: "
                f"{contract.asset.name}/{contract.quote_name} — "
                f"fetching before {before_timestamp or 'beginning'}"
            )

            points = await self._exchange_adapter.fetch_history_before(contract, before_timestamp)

            if not points:
                async with self._db.begin() as session:
                    merged_contract = await session.merge(contract)
                    merged_contract.synced = True
                logger.info(
                    f"[{self._section_name}] No more history for "
                    f"{contract.asset.name}/{contract.quote_name}, marking as synced "
                    f"(total batches: {batch_count}, total points: {total_points})"
                )
                break

            funding_records = [
                HistoricalFundingPoint(
                    contract_id=contract.id,
                    timestamp=point.timestamp,
                    funding_rate=point.rate,
                )
                for point in points
            ]

            async with self._db.begin() as session:
                await bulk_insert(
                    session, HistoricalFundingPoint, funding_records, on_conflict="ignore"
                )

            batch_points = len(points)
            total_points += batch_points

            logger.debug(
                f"[{self._section_name}] Sync batch #{batch_count}: "
                f"{contract.asset.name}/{contract.quote_name} — "
                f"{batch_points} points (oldest: {min(p.timestamp for p in points)}, "
                f"newest: {max(p.timestamp for p in points)})"
            )

            if batch_count % PROGRESS_LOG_BATCH_INTERVAL == 0:
                logger.info(
                    f"[{self._section_name}] Sync progress for "
                    f"{contract.asset.name}/{contract.quote_name}: "
                    f"batch #{batch_count}, {total_points} total points fetched, "
                    f"latest batch range: {min(p.timestamp for p in points)} to "
                    f"{max(p.timestamp for p in points)}"
                )

        return total_points

    async def _update_contract(self, contract: Contract) -> int:
        """Fetch new data after latest point; skip if funding interval not elapsed.

        NOTE: Holds DB session open during API call. Intentionally not fixed
        in this refactor — see _sync_contract for the correct pattern.
        """
        logger.debug(
            f"[{self._section_name}] Checking update for "
            f"{contract.asset.name}/{contract.quote_name}"
        )

        async with self._db.begin() as session:
            newest = await get_newest_for_contract(session, contract.id)
            after_timestamp = newest.timestamp + timedelta(seconds=1) if newest else None

            if after_timestamp is None:
                logger.warning(
                    f"[{self._section_name}] No historical data for "
                    f"{contract.asset.name}/{contract.quote_name}, run sync first"
                )
                return 0

            now = datetime.now()
            time_since_last = now - after_timestamp
            required_interval = timedelta(hours=contract.funding_interval)

            if time_since_last < required_interval:
                logger.debug(
                    f"[{self._section_name}] Skipping update for "
                    f"{contract.asset.name}/{contract.quote_name}, "
                    f"only {time_since_last} passed (need {required_interval})"
                )
                return 0

            points = await self._exchange_adapter.fetch_history_after(contract, after_timestamp)

            if not points:
                return 0

            funding_records = [
                HistoricalFundingPoint(
                    contract_id=contract.id,
                    timestamp=point.timestamp,
                    funding_rate=point.rate,
                )
                for point in points
            ]

            await bulk_insert(
                session, HistoricalFundingPoint, funding_records, on_conflict="ignore"
            )

            return len(points)

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------

    def _log_update_stats(
        self,
        contracts: Sequence[Contract],
        results: list[tuple[int, int]],
        start_time: datetime,
    ) -> None:
        """Aggregate and log statistics from contract processing."""
        updated_count = sum(r[0] for r in results)
        total_points = sum(r[1] for r in results)
        duration = datetime.now() - start_time
        logger.info(
            f"History update for {self._section_name}: "
            f"{updated_count} contracts updated ({total_points} new points), "
            f"{len(contracts) - updated_count} unchanged, "
            f"completed in {duration}"
        )
