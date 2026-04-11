"""Utility functions for database operations."""

from collections.abc import Iterable
from typing import Any, Literal, cast

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel


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
