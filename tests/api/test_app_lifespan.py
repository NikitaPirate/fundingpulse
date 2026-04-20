from __future__ import annotations

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.api.db import APP_SESSION_FACTORY_KEY, get_session
from fundingpulse.api.main import create_app
from fundingpulse.testing.db import DatabaseConfig


@pytest.mark.asyncio
async def test_app_lifespan_installs_session_dependency(fda_db_env: DatabaseConfig) -> None:
    app = create_app()

    async with app.router.lifespan_context(app):
        assert hasattr(app.state, APP_SESSION_FACTORY_KEY)

        request = Request(
            {
                "type": "http",
                "app": app,
                "headers": [],
                "query_string": b"",
                "method": "GET",
                "path": "/health",
            }
        )
        async for session in get_session(request):
            assert isinstance(session, AsyncSession)
            break

    assert not hasattr(app.state, APP_SESSION_FACTORY_KEY)
