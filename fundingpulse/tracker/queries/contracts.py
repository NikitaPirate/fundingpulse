"""Contract query functions."""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import select
from sqlmodel import col

from fundingpulse.models.contract import Contract


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


async def get_active_by_section_with_history_state(
    session: AsyncSession, section_name: str
) -> Sequence[Contract]:
    """Returns non-deprecated contracts with tracker history state loaded."""
    stmt = (
        select(Contract)
        .options(selectinload(cast(Any, Contract.history_state)))
        .where(
            col(Contract.section_name) == section_name,
            col(Contract.deprecated).is_(False),
        )
    )
    result = await session.execute(stmt)
    return result.scalars().all()
