"""Utility functions for repository operations."""

from collections.abc import Iterable, Sequence
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import asc, desc, select
from sqlmodel import SQLModel

from fundingpulse.models.base import NameModel, UUIDModel


class SQLModelWithTable(SQLModel):
    """Protocol for SQLModel instances that have a __table__ attribute."""

    __table__: Any


async def bulk_insert[M: SQLModel](
    session: AsyncSession,
    model: type[M],
    records: Iterable[M],
    conflict_target: list[str] | None = None,
    on_conflict: Literal["ignore", "update"] | None = None,
    update_fields: list[str] | None = None,
    chunk_size: int = 1000,
) -> None:
    """Insert multiple records with optional conflict handling.

    Args:
        session: Database session
        model: SQLModel class
        records: Iterable of model instances to insert
        conflict_target: Columns for conflict detection (required for on_conflict='update')
        on_conflict: Conflict resolution strategy ('ignore' or 'update')
        update_fields: Fields to update on conflict (required for on_conflict='update')
        chunk_size: Number of records to insert per query

    Raises:
        ValueError: If on_conflict='update' but conflict_target or update_fields not provided
    """
    records_list = list(records)
    if not records_list:
        return

    model_cls_with_table = cast(type[SQLModelWithTable], model)
    table_columns = model_cls_with_table.__table__.columns

    values = [
        {
            column.key: getattr(record, column.key)
            for column in table_columns
            if hasattr(record, column.key)
        }
        for record in records_list
    ]

    for i in range(0, len(values), chunk_size):
        chunk = values[i : i + chunk_size]
        stmt = pg_insert(model_cls_with_table.__table__).values(chunk)

        if on_conflict == "ignore":
            stmt = stmt.on_conflict_do_nothing()
        elif on_conflict == "update":
            if not conflict_target or not update_fields:
                raise ValueError(
                    "conflict_target and update_fields are required for on_conflict='update'"
                )
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_target,
                set_={field: getattr(stmt.excluded, field) for field in update_fields},
            )

        await session.execute(stmt)

    await session.flush()


async def get_by_uuid(
    session: AsyncSession,
    model: type[UUIDModel],
    id: UUID,
) -> UUIDModel | None:
    """Get a single record by UUID primary key.

    Args:
        session: Database session
        model: Model class with UUID primary key
        id: UUID to search for

    Returns:
        Model instance or None if not found
    """
    stmt = select(model).where(model.id == id)  # type: ignore[arg-type]
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_uuids(
    session: AsyncSession,
    model: type[UUIDModel],
    ids: list[UUID],
) -> Sequence[UUIDModel]:
    """Get multiple records by UUID primary keys.

    Args:
        session: Database session
        model: Model class with UUID primary key
        ids: List of UUIDs to search for

    Returns:
        Sequence of model instances
    """
    stmt = select(model).where(model.id.in_(ids))  # type: ignore[arg-type]
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_by_name(
    session: AsyncSession,
    model: type[NameModel],
    name: str,
) -> NameModel | None:
    """Get a single record by name primary key.

    Args:
        session: Database session
        model: Model class with name primary key
        name: Name to search for

    Returns:
        Model instance or None if not found
    """
    stmt = select(model).where(model.name == name)  # type: ignore[arg-type]
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_names(
    session: AsyncSession,
    model: type[NameModel],
    names: list[str],
) -> Sequence[NameModel]:
    """Get multiple records by name primary keys.

    Args:
        session: Database session
        model: Model class with name primary key
        names: List of names to search for

    Returns:
        Sequence of model instances
    """
    stmt = select(model).where(model.name.in_(names))  # type: ignore[arg-type]
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_last_record[T: SQLModel](
    session: AsyncSession,
    model: type[T],
    timestamp_column: str = "timestamp",
) -> T | None:
    """Get the most recent record ordered by timestamp.

    Args:
        session: Database session
        model: Model class with timestamp column
        timestamp_column: Name of the timestamp column (default: 'timestamp')

    Returns:
        Most recent model instance or None if no records
    """
    stmt = select(model).order_by(desc(getattr(model, timestamp_column))).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_first_record[T: SQLModel](
    session: AsyncSession,
    model: type[T],
    timestamp_column: str = "timestamp",
) -> T | None:
    """Get the oldest record ordered by timestamp.

    Args:
        session: Database session
        model: Model class with timestamp column
        timestamp_column: Name of the timestamp column (default: 'timestamp')

    Returns:
        Oldest model instance or None if no records
    """
    stmt = select(model).order_by(asc(getattr(model, timestamp_column))).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
