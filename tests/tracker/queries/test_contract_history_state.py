from collections.abc import Awaitable
from datetime import timedelta
from typing import Protocol

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.testing.helpers.data_helpers import get_or_create_asset, get_or_create_section
from fundingpulse.time import utc_now
from fundingpulse.tracker.queries import contract_history_state


class ContractFactory(Protocol):
    def __call__(
        self,
        asset_name: str = "BTC",
        section_name: str = "CEX",
        quote_name: str = "USDT",
        funding_interval: int = 8,
    ) -> Awaitable[Contract]: ...


async def _mk_deps(session: AsyncSession, asset: str, section: str) -> None:
    await get_or_create_asset(session, asset)
    await get_or_create_section(session, section)


@pytest.mark.asyncio
async def test_create_missing_for_section_creates_missing_state_rows_idempotently(
    db_session: AsyncSession,
) -> None:
    await _mk_deps(db_session, "BTC", "state_ex")
    db_session.add(
        Contract(
            asset_name="BTC",
            section_name="state_ex",
            quote_name="USDT",
            funding_interval=8,
        )
    )
    await db_session.commit()

    await contract_history_state.create_missing_for_section(db_session, "state_ex")
    await contract_history_state.create_missing_for_section(db_session, "state_ex")
    await db_session.commit()

    result = await db_session.execute(select(func.count()).select_from(ContractHistoryState))
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_update_bounds_is_monotonic(
    db_session: AsyncSession,
    contract_factory: ContractFactory,
) -> None:
    contract = await contract_factory(
        asset_name="BTC",
        section_name="bounds_ex",
        quote_name="USDT",
        funding_interval=8,
    )
    initial = utc_now() - timedelta(days=5)
    older = initial - timedelta(days=1)
    newer = initial + timedelta(days=1)

    state = await db_session.get(ContractHistoryState, contract.id)
    assert state is not None
    state.oldest_timestamp = initial
    state.newest_timestamp = initial
    await db_session.commit()

    await contract_history_state.update_bounds(
        db_session,
        contract.id,
        oldest_timestamp=older,
        newest_timestamp=newer,
    )
    await contract_history_state.update_bounds(
        db_session,
        contract.id,
        oldest_timestamp=initial,
        newest_timestamp=initial,
    )
    await db_session.commit()
    await db_session.refresh(state)

    assert state.oldest_timestamp == older
    assert state.newest_timestamp == newer
