from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, cast

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.live.constants import LIVE_FUNDING_PIPELINE, TASK_STATUS_PENDING
from fundingpulse.ingestion.live.enqueuer import enqueue_live_funding_tick
from fundingpulse.ingestion.scheduler import bootstrap_scheduler
from fundingpulse.ingestion.settings import IngestionLiveSettings
from tests.ingestion.live.helpers import all_ingestion_tasks


@pytest_asyncio.fixture()
async def ingestion_session_factory(
    engine: AsyncEngine,
    db_session: AsyncSession,
    db_session_kwargs: dict[str, object],
) -> AsyncGenerator[SessionFactory]:
    del db_session
    yield cast(SessionFactory, async_sessionmaker(engine, **db_session_kwargs))  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.db
async def test_scheduler_enqueue_job_creates_live_tasks(
    ingestion_session_factory: SessionFactory,
    db_session: AsyncSession,
) -> None:
    scheduler = bootstrap_scheduler(
        session_factory=ingestion_session_factory,
        exchanges=["bybit"],
        live_config=IngestionLiveSettings().to_enqueuer_config(),
    )
    live_enqueue_jobs = [
        job for job in scheduler.get_jobs() if job.func is enqueue_live_funding_tick
    ]
    assert len(live_enqueue_jobs) == 1

    job = live_enqueue_jobs[0]
    job_func = cast(Callable[..., Awaitable[Any]], job.func)
    await job_func(**job.kwargs)

    tasks = await all_ingestion_tasks(db_session)
    assert [(task.pipeline, task.exchange_name, task.status) for task in tasks] == [
        (LIVE_FUNDING_PIPELINE, "bybit", TASK_STATUS_PENDING),
    ]
