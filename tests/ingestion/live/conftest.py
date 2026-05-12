from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fundingpulse.db import SessionFactory


@pytest_asyncio.fixture()
async def ingestion_session_factory(
    engine: AsyncEngine,
    db_session: AsyncSession,
    db_session_kwargs: dict[str, object],
) -> AsyncGenerator[SessionFactory]:
    del db_session
    yield cast(SessionFactory, async_sessionmaker(engine, **db_session_kwargs))  # type: ignore[arg-type]
