"""Live funding rate collector."""

import logging
from typing import TYPE_CHECKING

from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.tracker.db import UOWFactoryType

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


async def collect_live(
    exchange_adapter: BaseExchange,
    section_name: str,
    uow_factory: UOWFactoryType,
) -> None:
    """Collect unsettled rates for given exchange section."""
    async with uow_factory() as uow:
        contracts = await uow.contracts.get_active_by_section(section_name)

    if not contracts:
        exchange_adapter.logger_live.warning("No active contracts found")
        return

    exchange_adapter.logger_live.debug(f"Collecting live rates for {len(contracts)} contracts")

    rates_by_contract = await exchange_adapter.fetch_live(list(contracts))

    if not rates_by_contract:
        exchange_adapter.logger_live.warning("No live rates collected")
        return

    live_records = [
        LiveFundingPoint(
            contract_id=contract.id,
            timestamp=rate.timestamp,
            funding_rate=rate.rate,
        )
        for contract, rate in rates_by_contract.items()
    ]

    async with uow_factory() as uow:
        await uow.live_funding_records.bulk_insert_ignore(live_records)

    success_count = len(live_records)
    failure_count = len(contracts) - success_count

    if failure_count > 0:
        logger.info(
            f"Live rate collection for {section_name}: "
            f"{success_count} success, {failure_count} failed"
        )
    else:
        logger.debug(
            f"Live rate collection for {section_name}: "
            f"all {success_count} rates collected successfully"
        )
