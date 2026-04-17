"""Shared database runtime for application-owned SQLAlchemy resources."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy_timescaledb  # noqa: F401 needed for dialect registration
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SessionFactory = async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class DBRuntimeConfig:
    """Resolved DB runtime configuration for one process."""

    connection_url: str
    engine_kwargs: dict[str, Any] = field(default_factory=dict)
    session_kwargs: dict[str, Any] = field(default_factory=dict)


@asynccontextmanager
async def db_session_factory_scope(config: DBRuntimeConfig) -> AsyncIterator[SessionFactory]:
    """Create a session factory for the caller's lifecycle and dispose it on exit."""
    engine = create_async_engine(config.connection_url, **config.engine_kwargs)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        **config.session_kwargs,  # type: ignore[arg-type]
    )
    try:
        yield session_factory
    finally:
        await engine.dispose()
