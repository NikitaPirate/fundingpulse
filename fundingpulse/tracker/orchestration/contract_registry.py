"""Reconcile the exchange's published contract list with the database.

Runs once per exchange per update cycle, before history processing. Ensures
that every asset/quote referenced by the exchange exists as a row, then
applies explicit contract lifecycle changes: add, deprecate, reactivate, and
funding-interval update.

The materialized view that powers the public API depends on the contract
table, so any contract plan change fires a debounced refresh signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.db import SessionFactory
from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.models.quote import Quote
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ContractInfo
from fundingpulse.tracker.orchestration.section_logger import SectionLogger
from fundingpulse.tracker.queries import contract_history_state
from fundingpulse.tracker.queries import contracts as contract_queries
from fundingpulse.tracker.queries.utils import bulk_insert

ContractKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class FundingIntervalChange:
    contract: Contract
    new_interval: int


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    added: tuple[ContractInfo, ...] = ()
    deprecated: tuple[Contract, ...] = ()
    reactivated: tuple[Contract, ...] = ()
    interval_changes: tuple[FundingIntervalChange, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.deprecated or self.reactivated or self.interval_changes)


class ContractChangeNotifier(Protocol):
    def signal_contracts_changed(self, exchange_name: str) -> None: ...


async def register_contracts(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    mv_refresher: ContractChangeNotifier,
    logger: SectionLogger,
) -> None:
    """Sync contract list from exchange API to DB.

    Raises any underlying exception — the caller decides whether a failed
    registration should abort the rest of the update cycle.
    """
    logger.debug("Starting contract sync")

    api_contracts = await adapter.get_contracts()
    logger.debug("Fetched %d contracts from API", len(api_contracts))

    if not api_contracts:
        logger.warning("No contracts returned from API")
        return

    async with db.begin() as session:
        await _ensure_quotes_and_assets(session, api_contracts, logger)
        existing = await contract_queries.get_by_section(session, section_name)
        logger.debug("Found %d existing contracts in DB", len(existing))
        plan = _reconcile(existing, api_contracts)
        await _apply_plan(session, section_name, plan)
        await contract_history_state.create_missing_for_section(session, section_name)

    logger.info(
        "Contract sync completed: %d feed, %d added, %d deprecated, "
        "%d reactivated, %d interval changes",
        len(api_contracts),
        len(plan.added),
        len(plan.deprecated),
        len(plan.reactivated),
        len(plan.interval_changes),
    )

    if plan.has_changes:
        mv_refresher.signal_contracts_changed(section_name)
        logger.debug("Signaled MV refresher")
    else:
        logger.debug("No contract changes detected; MV refresh not signaled")


def _reconcile(
    existing: Sequence[Contract],
    feed: Sequence[ContractInfo],
) -> ReconciliationPlan:
    """Calculate explicit lifecycle changes between DB contracts and exchange feed."""
    feed_by_key = _feed_by_key(feed)
    existing_by_key = {(c.asset_name, c.quote_name): c for c in existing}

    added = tuple(contract for key, contract in feed_by_key.items() if key not in existing_by_key)
    deprecated = tuple(
        contract
        for key, contract in existing_by_key.items()
        if key not in feed_by_key and not contract.deprecated
    )
    reactivated = tuple(
        contract
        for key, contract in existing_by_key.items()
        if key in feed_by_key and contract.deprecated
    )
    interval_changes = tuple(
        FundingIntervalChange(
            contract=contract,
            new_interval=feed_by_key[key].funding_interval,
        )
        for key, contract in existing_by_key.items()
        if key in feed_by_key and contract.funding_interval != feed_by_key[key].funding_interval
    )
    return ReconciliationPlan(
        added=added,
        deprecated=deprecated,
        reactivated=reactivated,
        interval_changes=interval_changes,
    )


def _feed_by_key(feed: Sequence[ContractInfo]) -> dict[ContractKey, ContractInfo]:
    by_key: dict[ContractKey, ContractInfo] = {}
    for contract in feed:
        key = (contract.asset_name, contract.quote)
        if key in by_key:
            asset_name, quote_name = key
            raise ValueError(f"Duplicate contract feed key: {asset_name}/{quote_name}")
        by_key[key] = contract
    return by_key


async def _ensure_quotes_and_assets(
    session: AsyncSession,
    api_contracts: list[ContractInfo],
    logger: SectionLogger,
) -> None:
    """Upsert the asset/quote rows that the contracts reference as FK targets."""
    quotes = {Quote(name=c.quote) for c in api_contracts}
    assets = {Asset(name=c.asset_name) for c in api_contracts}

    await bulk_insert(session, Quote, quotes, on_conflict="ignore")
    logger.debug("Inserted %d unique quotes", len(quotes))

    await bulk_insert(session, Asset, assets, on_conflict="ignore")
    logger.debug("Inserted %d unique assets", len(assets))


async def _apply_plan(
    session: AsyncSession,
    section_name: str,
    plan: ReconciliationPlan,
) -> None:
    """Persist a precomputed reconciliation plan without reclassifying operations."""
    added_rows = [
        Contract(
            asset_name=contract.asset_name,
            quote_name=contract.quote,
            section_name=section_name,
            funding_interval=contract.funding_interval,
            deprecated=False,
        )
        for contract in plan.added
    ]
    await bulk_insert(session, Contract, added_rows)

    for contract in plan.deprecated:
        contract.deprecated = True

    for contract in plan.reactivated:
        contract.deprecated = False

    for change in plan.interval_changes:
        change.contract.funding_interval = change.new_interval
