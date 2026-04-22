"""Contract history state query functions."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import case, false, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select, update
from sqlmodel import col

from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.time import UtcDateTime, utc_now


async def create_missing_for_section(session: AsyncSession, section_name: str) -> None:
    """Create missing history state rows for all contracts in a section."""
    state_table = cast(Any, ContractHistoryState).__table__
    stmt = pg_insert(state_table).from_select(
        ["contract_id", "history_synced", "updated_at"],
        select(
            col(Contract.id),
            false(),
            func.now(),
        ).where(col(Contract.section_name) == section_name),
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["contract_id"])
    await session.execute(stmt)
    await session.flush()


async def update_bounds(
    session: AsyncSession,
    contract_id: UUID,
    *,
    oldest_timestamp: UtcDateTime | None = None,
    newest_timestamp: UtcDateTime | None = None,
) -> None:
    """Move stored history bounds monotonically after a committed funding batch."""
    oldest_column = col(ContractHistoryState.oldest_timestamp)
    newest_column = col(ContractHistoryState.newest_timestamp)
    values: dict[str, object] = {"updated_at": utc_now()}

    if oldest_timestamp is not None:
        values["oldest_timestamp"] = case(
            (oldest_column.is_(None), oldest_timestamp),
            else_=func.least(oldest_column, oldest_timestamp),
        )

    if newest_timestamp is not None:
        values["newest_timestamp"] = case(
            (newest_column.is_(None), newest_timestamp),
            else_=func.greatest(newest_column, newest_timestamp),
        )

    if len(values) == 1:
        return

    await _execute_state_update(session, contract_id, values)


async def mark_history_synced(session: AsyncSession, contract_id: UUID) -> None:
    """Mark the contract's historical backfill as complete."""
    await _execute_state_update(
        session,
        contract_id,
        {
            "history_synced": True,
            "updated_at": utc_now(),
        },
    )


async def _execute_state_update(
    session: AsyncSession,
    contract_id: UUID,
    values: dict[str, object],
) -> None:
    stmt = (
        update(ContractHistoryState)
        .where(col(ContractHistoryState.contract_id) == contract_id)
        .values(**values)
    )
    result = await session.execute(stmt)
    if cast(Any, result).rowcount != 1:
        raise RuntimeError(f"Missing contract history state for contract {contract_id}")
    await session.flush()
