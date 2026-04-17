"""Database engine and session management.

Importing this module does not create DB resources. The FastAPI app owns the
session factory via lifespan and exposes only the session dependency to
handlers.
"""

from collections.abc import AsyncGenerator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.db import SessionFactory

APP_SESSION_FACTORY_KEY = "api_session_factory"


async def open_session(session_factory: SessionFactory) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def get_session(request: Request) -> AsyncGenerator[AsyncSession]:
    session_factory = getattr(request.app.state, APP_SESSION_FACTORY_KEY, None)
    if session_factory is None:
        raise RuntimeError("Database session factory is not initialized for this app instance")

    async for session in open_session(cast(SessionFactory, session_factory)):
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
