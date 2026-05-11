from __future__ import annotations

from argparse import Namespace
from typing import cast

import pytest

from fundingpulse.db import DBRuntimeConfig, SessionFactory
from fundingpulse.db_settings import DBSettings
from fundingpulse.exchange_selection import ExchangeSelectionSettings
from fundingpulse.tracker.bootstrap import bootstrap
from fundingpulse.tracker.exchanges import EXCHANGES
from fundingpulse.tracker.main import _http_max_connections_for_exchanges
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
        db_tuning=TrackerDBTuning(
            engine_kwargs={"pool_size": 99},
            session_kwargs={},
        ),
        exchange_selection=ExchangeSelectionSettings.model_construct(enabled_exchanges=None),
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
    assert config.db.session_kwargs == {"expire_on_commit": False}


def test_build_runtime_config_rejects_unknown_enabled_exchange() -> None:
    settings = Settings(
        db=DBSettings.model_construct(
            host="localhost",
            port=5432,
            user="tracker",
            password="tracker",
            dbname="fundingpulse",
        ),
        db_tuning=TrackerDBTuning(),
        exchange_selection=ExchangeSelectionSettings.model_construct(
            enabled_exchanges=("bybit", "missing")
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

    with pytest.raises(ValueError, match="ENABLED_EXCHANGES contains unknown exchange IDs"):
        build_runtime_config(args=args, settings=settings, all_exchanges={"bybit", "okx"})


def test_build_runtime_config_cli_exchanges_override_enabled_exchanges() -> None:
    settings = Settings(
        db=DBSettings.model_construct(
            host="localhost",
            port=5432,
            user="tracker",
            password="tracker",
            dbname="fundingpulse",
        ),
        db_tuning=TrackerDBTuning(),
        exchange_selection=ExchangeSelectionSettings.model_construct(
            enabled_exchanges=("okx",)
        ),
        app=TrackerAppSettings.model_construct(),
    )
    args = Namespace(
        exchanges="bybit",
        debug_exchanges=None,
        debug_exchanges_live=None,
        instance_id=None,
        total_instances=None,
    )

    config = build_runtime_config(args=args, settings=settings, all_exchanges={"bybit", "okx"})

    assert config.exchanges == ["bybit"]


def test_build_runtime_config_rejects_duplicate_cli_exchanges() -> None:
    settings = Settings(
        db=DBSettings.model_construct(
            host="localhost",
            port=5432,
            user="tracker",
            password="tracker",
            dbname="fundingpulse",
        ),
        db_tuning=TrackerDBTuning(),
        exchange_selection=ExchangeSelectionSettings.model_construct(enabled_exchanges=None),
        app=TrackerAppSettings.model_construct(),
    )
    args = Namespace(
        exchanges="bybit,bybit",
        debug_exchanges=None,
        debug_exchanges_live=None,
        instance_id=None,
        total_instances=None,
    )

    with pytest.raises(ValueError, match="--exchanges contains duplicate exchange IDs"):
        build_runtime_config(args=args, settings=settings, all_exchanges={"bybit", "okx"})


def test_http_max_connections_scales_with_exchange_assignment() -> None:
    single_exchange_limit = _http_max_connections_for_exchanges(["bybit"])

    assert _http_max_connections_for_exchanges([]) == single_exchange_limit
    assert _http_max_connections_for_exchanges(["bybit", "okx", "lighter"]) == (
        single_exchange_limit * 3
    )
    assert _http_max_connections_for_exchanges(None) == (single_exchange_limit * len(EXCHANGES))


def test_build_runtime_config_rejects_expiring_tracker_sessions() -> None:
    with pytest.raises(ValueError, match="expire_on_commit=False"):
        TrackerDBTuning(
            session_kwargs={"expire_on_commit": True},
        )


@pytest.mark.asyncio
async def test_bootstrap_uses_provided_session_factory() -> None:
    session_factory = cast(SessionFactory, object())

    scheduler = await bootstrap(session_factory=session_factory, exchanges=[])

    jobs = {job.name for job in scheduler.get_jobs()}
    assert jobs == {"materialized_views_refresher", "asset_ranking_update"}
