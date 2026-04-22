from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import col

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.models.quote import Quote
from fundingpulse.testing.helpers.data_helpers import create_contract, get_or_create_section
from fundingpulse.tracker.contracts import RegisteredContract, TrackedContract
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import ExchangeContractListing, FundingPoint
from fundingpulse.tracker.orchestration.contract_registry import (
    FundingIntervalChange,
    ReconciliationPlan,
    _reconcile,
    register_contracts,
)
from fundingpulse.tracker.orchestration.section_logger import make_section_logger

_SECTION = "registry_ex"


class _RegistryExchange(BaseExchange):
    EXCHANGE_ID = _SECTION
    _FETCH_STEP = 8

    def __init__(self, listings: Sequence[ExchangeContractListing]) -> None:
        super().__init__()
        self._listings = list(listings)

    def _format_symbol(self, contract: TrackedContract) -> str:
        return contract.asset_name

    async def get_contracts(self) -> list[ExchangeContractListing]:
        return list(self._listings)

    async def _fetch_history(
        self,
        contract: TrackedContract,
        start_ms: int,
        end_ms: int,
    ) -> list[FundingPoint]:
        raise NotImplementedError


class _FakeRefresher:
    def __init__(self) -> None:
        self.signals: list[str] = []

    def signal_contracts_changed(self, exchange_name: str) -> None:
        self.signals.append(exchange_name)


def _feed(
    asset_name: str, funding_interval: int = 8, quote_name: str = "USDT"
) -> ExchangeContractListing:
    return ExchangeContractListing(
        asset_name=asset_name,
        quote_name=quote_name,
        funding_interval=funding_interval,
        section_name=_SECTION,
    )


def _contract(
    asset_name: str,
    *,
    funding_interval: int = 8,
    quote_name: str = "USDT",
    deprecated: bool = False,
) -> RegisteredContract:
    return RegisteredContract(
        id=uuid4(),
        asset_name=asset_name,
        section_name=_SECTION,
        quote_name=quote_name,
        funding_interval=funding_interval,
        deprecated=deprecated,
    )


def _session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def _run_register(
    engine: AsyncEngine,
    feed: Sequence[ExchangeContractListing],
) -> _FakeRefresher:
    refresher = _FakeRefresher()
    await register_contracts(
        adapter=_RegistryExchange(feed),
        section_name=_SECTION,
        db=_session_factory(engine),
        mv_refresher=refresher,
        logger=make_section_logger(__name__, _SECTION),
    )
    return refresher


async def _load_contract(session: AsyncSession, asset_name: str) -> Contract:
    result = await session.execute(
        select(Contract).where(
            col(Contract.section_name) == _SECTION,
            col(Contract.asset_name) == asset_name,
        )
    )
    return result.scalar_one()


def test_reconcile_new_feed_against_empty_db_produces_added() -> None:
    feed = _feed("BTC")
    plan = _reconcile([], [feed])

    assert plan.added == (feed,)


def test_reconcile_unchanged_active_contract_produces_empty_plan() -> None:
    plan = _reconcile([_contract("BTC")], [_feed("BTC")])

    assert plan == ReconciliationPlan()
    assert plan.has_changes is False


def test_reconcile_missing_active_contract_produces_deprecated() -> None:
    contract = _contract("BTC")
    plan = _reconcile([contract], [])

    assert plan.deprecated == (contract,)
    assert plan.added == ()


def test_reconcile_already_deprecated_absent_from_feed_is_noop() -> None:
    """Deprecation is idempotent: we don't re-deprecate an already-deprecated row."""
    plan = _reconcile([_contract("LUNA", deprecated=True)], [])

    assert plan.has_changes is False


def test_reconcile_deprecated_contract_in_feed_produces_reactivated() -> None:
    contract = _contract("BTC", deprecated=True)
    plan = _reconcile([contract], [_feed("BTC")])

    assert plan.reactivated == (contract,)


def test_reconcile_active_contract_with_changed_interval_produces_interval_change() -> None:
    contract = _contract("BTC", funding_interval=8)
    plan = _reconcile([contract], [_feed("BTC", funding_interval=4)])

    assert plan.interval_changes == (FundingIntervalChange(contract, 4),)


def test_reconcile_reactivated_contract_can_also_change_interval() -> None:
    contract = _contract("BTC", funding_interval=8, deprecated=True)
    plan = _reconcile([contract], [_feed("BTC", funding_interval=4)])

    assert plan.reactivated == (contract,)
    assert plan.interval_changes == (FundingIntervalChange(contract, 4),)


def test_reconcile_quote_is_part_of_identity() -> None:
    """BTC/USDT and BTC/USDC are distinct contracts, not an interval-style edit."""
    btc_usdt = _contract("BTC", quote_name="USDT")

    plan = _reconcile([btc_usdt], [_feed("BTC", quote_name="USDC")])

    assert plan.deprecated == (btc_usdt,)
    assert [info.quote_name for info in plan.added] == ["USDC"]


def test_reconcile_combined_plan_mixes_all_four_operations() -> None:
    btc = _contract("BTC", funding_interval=8)  # interval change
    eth = _contract("ETH")  # deprecated
    luna = _contract("LUNA", deprecated=True)  # reactivated

    plan = _reconcile(
        [btc, eth, luna],
        [
            _feed("BTC", funding_interval=4),
            _feed("LUNA"),
            _feed("SOL"),  # added
        ],
    )

    assert [info.asset_name for info in plan.added] == ["SOL"]
    assert plan.deprecated == (eth,)
    assert plan.reactivated == (luna,)
    assert plan.interval_changes == (FundingIntervalChange(btc, 4),)


def test_reconcile_duplicate_feed_key_raises() -> None:
    with pytest.raises(ValueError, match="Duplicate contract feed key: BTC/USDT"):
        _reconcile([], [_feed("BTC", funding_interval=8), _feed("BTC", funding_interval=4)])


@pytest.mark.asyncio
async def test_register_new_contracts_creates_reference_rows_and_history_state(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    await get_or_create_section(db_session, _SECTION)

    refresher = await _run_register(engine, [_feed("BTC"), _feed("ETH", quote_name="USDC")])

    assets = (
        (await db_session.execute(select(col(Asset.name)).order_by(col(Asset.name))))
        .scalars()
        .all()
    )
    quotes = (
        (await db_session.execute(select(col(Quote.name)).order_by(col(Quote.name))))
        .scalars()
        .all()
    )
    contracts = (
        (await db_session.execute(select(Contract).order_by(col(Contract.asset_name))))
        .scalars()
        .all()
    )
    state_count = (
        await db_session.execute(select(func.count()).select_from(ContractHistoryState))
    ).scalar_one()

    assert assets == ["BTC", "ETH"]
    assert quotes == ["USDC", "USDT"]
    assert [(c.asset_name, c.quote_name, c.deprecated) for c in contracts] == [
        ("BTC", "USDT", False),
        ("ETH", "USDC", False),
    ]
    assert state_count == 2
    assert refresher.signals == [_SECTION]


@pytest.mark.asyncio
async def test_register_marks_missing_active_contract_deprecated(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    btc = await create_contract(db_session, "BTC", _SECTION, "USDT", 8)
    await create_contract(db_session, "ETH", _SECTION, "USDT", 8)

    refresher = await _run_register(engine, [_feed("ETH")])
    await db_session.refresh(btc)

    assert btc.deprecated is True
    assert refresher.signals == [_SECTION]


@pytest.mark.asyncio
async def test_register_reactivates_existing_contract_without_recreating_it(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(db_session, "BTC", _SECTION, "USDT", 8)
    contract.deprecated = True
    await db_session.commit()
    contract_id = contract.id

    refresher = await _run_register(engine, [_feed("BTC")])
    await db_session.refresh(contract)
    state_count = (
        await db_session.execute(select(func.count()).select_from(ContractHistoryState))
    ).scalar_one()

    assert contract.id == contract_id
    assert contract.deprecated is False
    assert state_count == 1
    assert refresher.signals == [_SECTION]


@pytest.mark.asyncio
async def test_register_interval_change_updates_only_interval(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    contract = await create_contract(db_session, "BTC", _SECTION, "USDT", 8)

    refresher = await _run_register(engine, [_feed("BTC", funding_interval=4)])
    await db_session.refresh(contract)

    assert contract.funding_interval == 4
    assert contract.deprecated is False
    assert refresher.signals == [_SECTION]


@pytest.mark.asyncio
async def test_register_noop_feed_does_not_signal_materialized_view_refresh(
    db_session: AsyncSession,
    engine: AsyncEngine,
) -> None:
    await create_contract(db_session, "BTC", _SECTION, "USDT", 8)

    refresher = await _run_register(engine, [_feed("BTC")])
    contract = await _load_contract(db_session, "BTC")

    assert contract.deprecated is False
    assert contract.funding_interval == 8
    assert refresher.signals == []
