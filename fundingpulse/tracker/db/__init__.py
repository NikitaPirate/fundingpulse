"""Database layer for funding tracker."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SessionFactory = async_sessionmaker[AsyncSession]


def setup_db_session(
    db_connection: str,
    session_kwargs: dict[str, Any] | None = None,
    engine_kwargs: dict[str, Any] | None = None,
) -> SessionFactory:
    """Create a SQLAlchemy async session factory."""
    session_kwargs = {"expire_on_commit": False, **(session_kwargs or {})}
    engine_kwargs = engine_kwargs or {}

    engine = create_async_engine(db_connection, **engine_kwargs)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        **session_kwargs,
    )
