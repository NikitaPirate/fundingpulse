"""Contract query functions."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select
from sqlmodel import col

from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.tracker.contracts import RegisteredContract, TrackedContract
from fundingpulse.tracker.history import ContractHistoryStateSnapshot


async def get_by_section(session: AsyncSession, section_name: str) -> Sequence[Contract]:
    stmt = select(Contract).where(Contract.section_name == section_name)  # type: ignore[arg-type]
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_active_by_section(session: AsyncSession, section_name: str) -> Sequence[Contract]:
    """Returns non-deprecated contracts only."""
    stmt = select(Contract).where(  # type: ignore[arg-type]
        Contract.section_name == section_name,  # type: ignore[arg-type]
        Contract.deprecated == False,  # type: ignore[arg-type]  # noqa: E712
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_registered_by_section(
    session: AsyncSession, section_name: str
) -> Sequence[RegisteredContract]:
    """Return contract rows needed to reconcile the registry feed."""
    stmt = select(Contract).where(col(Contract.section_name) == section_name)
    result = await session.execute(stmt)
    return [
        RegisteredContract(
            id=contract.id,
            asset_name=contract.asset_name,
            section_name=contract.section_name,
            quote_name=contract.quote_name,
            funding_interval=contract.funding_interval,
            deprecated=contract.deprecated,
        )
        for contract in result.scalars().all()
    ]


async def get_contract_history_state_snapshots_by_section(
    session: AsyncSession, section_name: str
) -> Sequence[tuple[TrackedContract, ContractHistoryStateSnapshot]]:
    """Return active contracts with existing tracker history-state snapshots.

    Contracts without a ContractHistoryState row are intentionally skipped:
    registry creates missing state rows, so the next tracker pass will pick
    them up after that repair.
    """
    stmt = (
        select(Contract, ContractHistoryState)
        .join(ContractHistoryState, col(Contract.id) == col(ContractHistoryState.contract_id))
        .where(
            col(Contract.section_name) == section_name,
            col(Contract.deprecated).is_(False),
        )
    )
    result = await session.execute(stmt)
    return [
        (
            TrackedContract(
                id=contract.id,
                asset_name=contract.asset_name,
                section_name=contract.section_name,
                quote_name=contract.quote_name,
                funding_interval=contract.funding_interval,
            ),
            ContractHistoryStateSnapshot(
                history_synced=state.history_synced,
                oldest_timestamp=state.oldest_timestamp,
                newest_timestamp=state.newest_timestamp,
            ),
        )
        for contract, state in result.all()
    ]


async def mark_deprecated(session: AsyncSession, contract_ids: Sequence[UUID]) -> None:
    await _set_deprecated(session, contract_ids, deprecated=True)


async def reactivate(session: AsyncSession, contract_ids: Sequence[UUID]) -> None:
    await _set_deprecated(session, contract_ids, deprecated=False)


async def set_funding_interval(
    session: AsyncSession,
    contract_id: UUID,
    funding_interval: int,
) -> None:
    stmt = (
        update(Contract)
        .where(col(Contract.id) == contract_id)
        .values(funding_interval=funding_interval)
    )
    await session.execute(stmt)


async def _set_deprecated(
    session: AsyncSession,
    contract_ids: Sequence[UUID],
    *,
    deprecated: bool,
) -> None:
    if not contract_ids:
        return

    stmt = update(Contract).where(col(Contract.id).in_(contract_ids)).values(deprecated=deprecated)
    await session.execute(stmt)
