"""Database engine and session management.

Importing this module does not create DB resources. The FastAPI app owns the
engine/session factory via lifespan and keeps them in app.state; SessionDep
remains the stable API for route handlers.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated, cast

import sqlalchemy_timescaledb  # noqa: F401 needed for dialect registration
from fastapi import Depends, FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from fundingpulse.api.settings import APIDBTuning, get_api_db_tuning
from fundingpulse.db_settings import DBSettings

SessionFactory = async_sessionmaker[AsyncSession]
_APP_DB_STATE_KEY = "api_db_resources"


@dataclass(frozen=True, slots=True)
class APIDBResources:
    engine: AsyncEngine
    session_factory: SessionFactory


def _engine_kwargs(tuning: APIDBTuning) -> dict[str, object]:
    defaults = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 50,
    }
    return {**defaults, **(tuning.engine_kwargs or {})}


def _session_kwargs(tuning: APIDBTuning) -> dict[str, object]:
    defaults = {"expire_on_commit": False}
    return {**defaults, **(tuning.session_kwargs or {})}


def create_db_resources() -> APIDBResources:
    tuning = get_api_db_tuning()
    engine = create_async_engine(
        DBSettings().connection_url,  # pyright: ignore[reportCallIssue]
        **_engine_kwargs(tuning),
    )
    session_factory = async_sessionmaker(
        engine,
        **_session_kwargs(tuning),  # type: ignore[arg-type]
    )
    return APIDBResources(engine=engine, session_factory=session_factory)


def install_db_resources(app: FastAPI) -> None:
    if hasattr(app.state, _APP_DB_STATE_KEY):
        return
    setattr(app.state, _APP_DB_STATE_KEY, create_db_resources())


async def dispose_db_resources(resources: APIDBResources) -> None:
    await resources.engine.dispose()


async def dispose_app_db(app: FastAPI) -> None:
    resources = getattr(app.state, _APP_DB_STATE_KEY, None)
    if resources is None:
        return
    await dispose_db_resources(cast(APIDBResources, resources))
    delattr(app.state, _APP_DB_STATE_KEY)


def get_app_db_resources(request: Request) -> APIDBResources:
    resources = getattr(request.app.state, _APP_DB_STATE_KEY, None)
    if resources is None:
        raise RuntimeError("Database resources are not initialized for this app instance")
    return cast(APIDBResources, resources)


async def open_session(session_factory: SessionFactory) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    async for session in open_session(get_app_db_resources(request).session_factory):
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
