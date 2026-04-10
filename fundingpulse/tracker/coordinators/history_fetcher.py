"""Historical funding data fetcher."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fundingpulse.models.contract import Contract
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.tracker.db import UOWFactoryType

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange

# Log progress every N batches during sync operations
PROGRESS_LOG_BATCH_INTERVAL = 10


async def sync_contract(
    exchange_adapter: BaseExchange,
    contract: Contract,
    uow_factory: UOWFactoryType,
) -> int:
    """Fetch backwards until no more data; marks contract as synced.

    Opens/closes session for each DB operation to avoid holding sessions open
    during long API calls.
    """
    if contract.synced:
        exchange_adapter.logger.debug(
            f"Contract {contract.asset.name}/{contract.quote_name} "
            f"on {contract.section_name} already synced, skipping"
        )
        return 0

    exchange_adapter.logger.debug(
        f"Starting sync for {contract.asset.name}/{contract.quote_name} on {contract.section_name}"
    )

    total_points = 0
    batch_count = 0

    while True:
        batch_count += 1

        async with uow_factory() as uow:
            oldest = await uow.historical_funding_records.get_oldest_for_contract(contract.id)
            # minus 1 second to avoid refetching the oldest point
            before_timestamp = oldest.timestamp - timedelta(seconds=1) if oldest else None

        exchange_adapter.logger.debug(
            f"Sync batch #{batch_count}: {contract.asset.name}/{contract.quote_name} - "
            f"fetching before {before_timestamp or 'beginning'}"
        )

        points = await exchange_adapter.fetch_history_before(contract, before_timestamp)

        if not points:
            async with uow_factory() as uow:
                merged_contract = await uow.merge(contract)
                merged_contract.synced = True
                await uow.commit()
            exchange_adapter.logger.info(
                f"No more history for {contract.asset.name}/{contract.quote_name}, "
                f"marking as synced (total batches: {batch_count}, total points: {total_points})"
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

        async with uow_factory() as uow:
            await uow.historical_funding_records.bulk_insert_ignore(funding_records)
            await uow.commit()

        batch_points = len(points)
        total_points += batch_points

        exchange_adapter.logger.debug(
            f"Sync batch #{batch_count}: {contract.asset.name}/{contract.quote_name} - "
            f"{batch_points} points (oldest: {min(p.timestamp for p in points)}, "
            f"newest: {max(p.timestamp for p in points)})"
        )

        # Log progress periodically
        if batch_count % PROGRESS_LOG_BATCH_INTERVAL == 0:
            exchange_adapter.logger.info(
                f"Sync progress for {contract.asset.name}/{contract.quote_name}: "
                f"batch #{batch_count}, {total_points} total points fetched, "
                f"latest batch range: {min(p.timestamp for p in points)} to "
                f"{max(p.timestamp for p in points)}"
            )

    return total_points


async def update_contract(
    exchange_adapter: BaseExchange,
    contract: Contract,
    uow_factory: UOWFactoryType,
) -> int:
    """Fetch new data after latest point; skips if interval not elapsed."""
    exchange_adapter.logger.debug(
        f"Checking update for {contract.asset.name}/{contract.quote_name} "
        f"on {contract.section_name}"
    )

    async with uow_factory() as uow:
        newest = await uow.historical_funding_records.get_newest_for_contract(contract.id)
        # add 1 second to avoid refetching already existing point
        after_timestamp = newest.timestamp + timedelta(seconds=1) if newest else None

        if after_timestamp is None:
            exchange_adapter.logger.warning(
                f"No historical data found for {contract.asset.name}/{contract.quote_name}, "
                f"run sync first"
            )
            return 0

        now = datetime.now()
        time_since_last = now - after_timestamp
        required_interval = timedelta(hours=contract.funding_interval)

        if time_since_last < required_interval:
            exchange_adapter.logger.debug(
                f"Skipping update for {contract.asset.name}/{contract.quote_name}, "
                f"only {time_since_last} passed (need {required_interval})"
            )
            return 0

        points = await exchange_adapter.fetch_history_after(contract, after_timestamp)

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

        await uow.historical_funding_records.bulk_insert_ignore(funding_records)

        return len(points)
