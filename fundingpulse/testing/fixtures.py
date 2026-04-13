from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from fundingpulse.models.contract import Contract
from fundingpulse.testing.db import (
    DEFAULT_TIMESCALE_IMAGE,
    DatabaseConfig,
    apply_alembic_migrations,
    timescaledb_container,
    truncate_all_tables,
)
from fundingpulse.testing.helpers.data_helpers import create_contract


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_image() -> str:
    return DEFAULT_TIMESCALE_IMAGE


@pytest.fixture(scope="session")
def db_config(
    db_image: str,
) -> Iterator[DatabaseConfig]:
    previous = {
        "DB_HOST": os.environ.get("DB_HOST"),
        "DB_PORT": os.environ.get("DB_PORT"),
        "DB_USER": os.environ.get("DB_USER"),
        "DB_PASSWORD": os.environ.get("DB_PASSWORD"),
        "DB_DBNAME": os.environ.get("DB_DBNAME"),
    }
    with timescaledb_container(db_image) as config:
        os.environ["DB_HOST"] = config.host
        os.environ["DB_PORT"] = str(config.port)
        os.environ["DB_USER"] = config.user
        os.environ["DB_PASSWORD"] = config.password
        os.environ["DB_DBNAME"] = config.dbname
        apply_alembic_migrations()
        yield config

    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="session")
def db_url(db_config: DatabaseConfig) -> str:
    return db_config.url


@pytest.fixture(scope="session")
def db_engine_kwargs() -> dict[str, object]:
    return {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }


@pytest.fixture(scope="session")
def db_session_kwargs() -> dict[str, object]:
    return {
        "expire_on_commit": False,
    }


@pytest.fixture(scope="session")
def db_truncate_exclude() -> set[str]:
    return {"alembic_version"}


@pytest_asyncio.fixture(scope="session")
async def engine(
    db_url: str,
    db_engine_kwargs: dict[str, object],
) -> AsyncGenerator[AsyncEngine]:
    db_engine = create_async_engine(db_url, **db_engine_kwargs)
    yield db_engine
    await db_engine.dispose()


@pytest_asyncio.fixture()
async def db_session(
    engine: AsyncEngine,
    db_session_kwargs: dict[str, object],
    db_truncate_exclude: set[str],
) -> AsyncGenerator[AsyncSession]:
    session_factory = async_sessionmaker(engine, **db_session_kwargs)  # type: ignore[arg-type]
    session = session_factory()
    try:
        yield session
    finally:
        await session.rollback()
        await truncate_all_tables(session, exclude=db_truncate_exclude)
        await session.close()


@pytest_asyncio.fixture()
async def contract_factory(
    db_session: AsyncSession,
) -> Callable[[str, str, str, int], Awaitable[Contract]]:
    async def _create_contract(
        asset_name: str = "BTC",
        section_name: str = "CEX",
        quote_name: str = "USDT",
        funding_interval: int = 8,
    ) -> Contract:
        return await create_contract(
            db_session,
            asset_name=asset_name,
            section_name=section_name,
            quote_name=quote_name,
            funding_interval=funding_interval,
        )

    return _create_contract
