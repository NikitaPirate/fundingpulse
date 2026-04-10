from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

import sqlalchemy_timescaledb  # noqa: F401 need for dialect registration
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from testcontainers.postgres import PostgresContainer

from fundingpulse.migrations.config import get_alembic_config

DEFAULT_TIMESCALE_IMAGE = "timescale/timescaledb:2.23.0-pg18"


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    host: str
    port: int
    user: str
    password: str
    dbname: str


def build_db_url(host: str, port: int, user: str, password: str, dbname: str) -> str:
    return f"timescaledb+psycopg://{user}:{password}@{host}:{port}/{dbname}"


def parse_container_url(sync_url: str) -> DatabaseConfig:
    url = make_url(sync_url)
    if not url.host or not url.port or not url.username or not url.password or not url.database:
        raise ValueError(f"Invalid database url: {sync_url}")

    db_url = build_db_url(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname=url.database,
    )
    return DatabaseConfig(
        url=db_url,
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname=url.database,
    )


@contextmanager
def timescaledb_container(image: str = DEFAULT_TIMESCALE_IMAGE) -> Iterator[DatabaseConfig]:
    with PostgresContainer(image) as postgres:
        raw_sync_url = postgres.get_connection_url()
        yield parse_container_url(raw_sync_url)


def apply_alembic_migrations() -> None:
    config = get_alembic_config()
    command.upgrade(config, "head")


async def truncate_all_tables(session: AsyncSession, exclude: set[str] | None = None) -> None:
    exclude = exclude or set()
    result = await session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
    )
    table_names = [row[0] for row in result.fetchall() if row[0] not in exclude]
    if not table_names:
        return

    table_list = ", ".join(f'"{name}"' for name in table_names)
    await session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;"))
    await session.commit()


async def refresh_materialized_views(engine: AsyncEngine, view_names: Sequence[str]) -> None:
    if not view_names:
        return

    async with engine.connect() as connection:
        autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
        for view_name in view_names:
            await autocommit.execute(text(f"REFRESH MATERIALIZED VIEW {view_name};"))
