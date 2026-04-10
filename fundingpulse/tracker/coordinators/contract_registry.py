"""Contract registry synchronizer."""

import logging
from typing import TYPE_CHECKING

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.models.quote import Quote
from fundingpulse.models.section import Section
from fundingpulse.tracker.db import UOWFactoryType
from fundingpulse.tracker.materialized_view_refresher import MaterializedViewRefresher

if TYPE_CHECKING:
    from fundingpulse.tracker.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


async def register_contracts(
    exchange_adapter: BaseExchange,
    section_name: str,
    uow_factory: UOWFactoryType,
    mv_refresher: MaterializedViewRefresher | None = None,
) -> None:
    """Sync contracts from API; marks missing as deprecated, signals MV refresher."""
    logger.debug(f"Starting contract sync for {section_name}")

    api_contracts = await exchange_adapter.get_contracts()
    logger.debug(f"Fetched {len(api_contracts)} contracts from {section_name} API")

    if not api_contracts:
        logger.warning(f"No contracts returned from {section_name} API")
        return

    async with uow_factory() as uow:
        section = Section(name=section_name)
        await uow.sections.bulk_insert_ignore([section])

        quotes = {Quote(name=contract.quote) for contract in api_contracts}
        await uow.quotes.bulk_insert_ignore(quotes)
        logger.debug(f"Inserted {len(quotes)} unique quotes")

        assets = {Asset(name=contract.asset_name) for contract in api_contracts}
        await uow.assets.bulk_insert_ignore(assets)
        logger.debug(f"Inserted {len(assets)} unique assets")

        existing_contracts = await uow.contracts.get_by_section(section_name)
        logger.debug(f"Found {len(existing_contracts)} existing contracts in DB")

        api_contract_keys = {(c.asset_name, c.quote) for c in api_contracts}

        deprecated_count = 0
        for contract in existing_contracts:
            if (contract.asset_name, contract.quote_name) not in api_contract_keys:
                contract.deprecated = True
                deprecated_count += 1

        if deprecated_count > 0:
            logger.debug(f"Marked {deprecated_count} contracts as deprecated")

        contracts_to_upsert = [
            Contract(
                asset_name=c.asset_name,
                quote_name=c.quote,
                section_name=section_name,
                funding_interval=c.funding_interval,
                deprecated=False,
            )
            for c in api_contracts
        ]

        await uow.contracts.upsert_many(contracts_to_upsert)
        await uow.commit()

        logger.info(
            f"Contract sync completed for {section_name}: "
            f"{len(api_contracts)} active, {deprecated_count} deprecated"
        )

    if mv_refresher is not None:
        await mv_refresher.signal_contracts_changed(section_name)
        logger.debug(f"Signaled MV refresher for {section_name}")
