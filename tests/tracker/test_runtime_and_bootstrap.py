from __future__ import annotations

from argparse import Namespace

import pytest

from fundingpulse.db import DBRuntimeConfig
from fundingpulse.db_settings import DBSettings
from fundingpulse.tracker.bootstrap import bootstrap
from fundingpulse.tracker.runtime import build_runtime_config
from fundingpulse.tracker.settings import Settings, TrackerAppSettings, TrackerDBTuning


def test_build_runtime_config_merges_db_runtime_overrides() -> None:
    settings = Settings(
        db=DBSettings.model_construct(
            host="localhost",
            port=5432,
            user="tracker",
            password="tracker",
            dbname="fundingpulse",
        ),
        db_tuning=TrackerDBTuning.model_construct(
            engine_kwargs={"pool_size": 99},
            session_kwargs={"expire_on_commit": True},
        ),
        app=TrackerAppSettings.model_construct(),
    )
    args = Namespace(
        exchanges=None,
        debug_exchanges=None,
        debug_exchanges_live=None,
        instance_id=None,
        total_instances=None,
    )

    config = build_runtime_config(args=args, settings=settings, all_exchanges={"bybit", "okx"})

    assert isinstance(config.db, DBRuntimeConfig)
    assert config.db.connection_url.startswith("timescaledb+psycopg://tracker:tracker@localhost:")
    assert config.db.engine_kwargs["pool_size"] == 99
    assert config.db.engine_kwargs["pool_pre_ping"] is True
    assert config.db.session_kwargs == {"expire_on_commit": True}


@pytest.mark.asyncio
async def test_bootstrap_uses_provided_session_factory() -> None:
    session_factory = object()

    scheduler = await bootstrap(session_factory=session_factory, exchanges=[])

    jobs = {job.name for job in scheduler.get_jobs()}
    assert jobs == {"materialized_views_refresher", "asset_ranking_update"}
