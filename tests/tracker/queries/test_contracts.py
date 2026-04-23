from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.testing.helpers.data_helpers import (
    create_contract,
    get_or_create_asset,
    get_or_create_section,
)
from fundingpulse.time import utc_now
from fundingpulse.tracker.queries.contracts import (
    get_active_by_section,
    get_contracts_with_history_state_by_section,
)


@pytest.mark.asyncio
async def test_get_contracts_with_history_state_returns_active_section_rows_with_state(
    db_session: AsyncSession,
) -> None:
    section_name = "history_query_ex"
    included = await create_contract(
        db_session,
        asset_name="BTC",
        section_name=section_name,
        quote_name="USDT",
        funding_interval=8,
    )
    oldest = utc_now() - timedelta(days=14)
    newest = utc_now() - timedelta(hours=8)
    included_state = await db_session.get(ContractHistoryState, included.id)
    assert included_state is not None
    included_state.history_synced = True
    included_state.oldest_timestamp = oldest
    included_state.newest_timestamp = newest

    deprecated = await create_contract(
        db_session,
        asset_name="ETH",
        section_name=section_name,
        quote_name="USDT",
        funding_interval=8,
    )
    deprecated.deprecated = True

    await create_contract(
        db_session,
        asset_name="SOL",
        section_name="other_history_query_ex",
        quote_name="USDT",
        funding_interval=8,
    )

    asset = await get_or_create_asset(db_session, "XRP")
    section = await get_or_create_section(db_session, section_name)
    db_session.add(
        Contract(
            asset_name=asset.name,
            section_name=section.name,
            quote_name="USDT",
            funding_interval=8,
        )
    )
    await db_session.commit()

    rows = list(await get_contracts_with_history_state_by_section(db_session, section_name))

    assert len(rows) == 1
    contract = rows[0].contract
    state = rows[0].state
    assert contract.id == included.id
    assert isinstance(contract, Contract)
    assert contract.asset_name == "BTC"
    assert contract.section_name == section_name
    assert contract.quote_name == "USDT"
    assert contract.funding_interval == 8
    assert isinstance(state, ContractHistoryState)
    assert state.history_synced is True
    assert state.oldest_timestamp == oldest
    assert state.newest_timestamp == newest


@pytest.mark.asyncio
async def test_get_active_by_section_returns_runtime_contracts(
    db_session: AsyncSession,
) -> None:
    section_name = "live_query_ex"
    included = await create_contract(
        db_session,
        asset_name="BTC",
        section_name=section_name,
        quote_name="USDT",
        funding_interval=8,
    )
    deprecated = await create_contract(
        db_session,
        asset_name="ETH",
        section_name=section_name,
        quote_name="USDT",
        funding_interval=4,
    )
    deprecated.deprecated = True
    await create_contract(
        db_session,
        asset_name="SOL",
        section_name="other_live_query_ex",
        quote_name="USDT",
        funding_interval=8,
    )
    await db_session.commit()

    contracts = list(await get_active_by_section(db_session, section_name))

    assert len(contracts) == 1
    contract = contracts[0]
    assert contract.id == included.id
    assert isinstance(contract, Contract)
    assert contract.asset_name == "BTC"
    assert contract.section_name == section_name
    assert contract.quote_name == "USDT"
    assert contract.funding_interval == 8
