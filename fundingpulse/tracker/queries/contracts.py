"""Contract query functions."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select
from sqlmodel import col

from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState


@dataclass(frozen=True, slots=True)
class ContractWithHistoryState:
    """Explicit query projection for a contract and its loaded tracker state."""

    contract: Contract
    state: ContractHistoryState


async def get_active_by_section(session: AsyncSession, section_name: str) -> Sequence[Contract]:
    """Return active contracts as detached scalar ORM rows."""
    stmt = select(Contract).where(
        col(Contract.section_name) == section_name,
        col(Contract.deprecated).is_(False),
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_by_section(session: AsyncSession, section_name: str) -> Sequence[Contract]:
    """Return all contract rows for a section."""
    stmt = select(Contract).where(col(Contract.section_name) == section_name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_contracts_with_history_state_by_section(
    session: AsyncSession, section_name: str
) -> Sequence[ContractWithHistoryState]:
    """Return active contracts with explicitly loaded tracker history state.

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
        ContractWithHistoryState(contract=contract, state=state)
        for contract, state in result.all()
    ]
