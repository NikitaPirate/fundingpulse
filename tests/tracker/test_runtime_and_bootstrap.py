from __future__ import annotations

from argparse import Namespace
from typing import cast

import pytest
from apscheduler.job import Job

from fundingpulse.db import DBRuntimeConfig, SessionFactory
from fundingpulse.db_settings import DBSettings
from fundingpulse.exchange_selection import ExchangeSelectionSettings
from fundingpulse.time import UtcDateTime, utc_datetime
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
    assert config.exchanges is None
    assert config.registry_exchanges == ["bybit", "okx"]
    assert config.owns_singleton_jobs is True


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
        exchange_selection=ExchangeSelectionSettings.model_construct(enabled_exchanges=("okx",)),
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
    assert config.registry_exchanges == ["bybit"]
    assert config.owns_singleton_jobs is True


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
    assert _http_max_connections_for_exchanges(["bybit"], ["bybit", "okx"]) == (
        single_exchange_limit * 2
    )
    assert _http_max_connections_for_exchanges(None) == (single_exchange_limit * len(EXCHANGES))


def test_build_runtime_config_assigns_singleton_jobs_to_instance_zero() -> None:
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
    all_exchanges = {"aster", "bybit", "okx", "paradex"}

    instance_zero = build_runtime_config(
        args=Namespace(
            exchanges=None,
            debug_exchanges=None,
            debug_exchanges_live=None,
            instance_id=0,
            total_instances=2,
        ),
        settings=settings,
        all_exchanges=all_exchanges,
    )
    instance_one = build_runtime_config(
        args=Namespace(
            exchanges=None,
            debug_exchanges=None,
            debug_exchanges_live=None,
            instance_id=1,
            total_instances=2,
        ),
        settings=settings,
        all_exchanges=all_exchanges,
    )

    assert instance_zero.exchanges == ["aster", "okx"]
    assert instance_zero.registry_exchanges == ["aster", "bybit", "okx", "paradex"]
    assert instance_zero.owns_singleton_jobs is True
    assert instance_one.exchanges == ["bybit", "paradex"]
    assert instance_one.registry_exchanges == []
    assert instance_one.owns_singleton_jobs is False


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


@pytest.mark.asyncio
async def test_bootstrap_registers_tracker_live_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ensure_sections(_: SessionFactory, __: list[str]) -> None:
        return None

    monkeypatch.setattr("fundingpulse.tracker.bootstrap._ensure_sections", ensure_sections)
    session_factory = cast(SessionFactory, object())

    scheduler = await bootstrap(
        session_factory=session_factory,
        exchanges=["bybit"],
    )

    jobs = {job.name for job in scheduler.get_jobs()}
    assert "bybit_history_backfill" in jobs
    assert "bybit_history_update" in jobs
    assert "bybit_update" not in jobs
    assert "bybit_live" in jobs


@pytest.mark.asyncio
async def test_bootstrap_registers_history_update_on_hourly_timing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ensure_sections(_: SessionFactory, __: list[str]) -> None:
        return None

    started_at = utc_datetime(2026, 1, 1, 0, 3)
    monkeypatch.setattr("fundingpulse.tracker.bootstrap._ensure_sections", ensure_sections)
    monkeypatch.setattr("fundingpulse.tracker.bootstrap.utc_now", lambda: started_at)
    session_factory = cast(SessionFactory, object())

    scheduler = await bootstrap(
        session_factory=session_factory,
        exchanges=["bybit"],
    )

    job = next(job for job in scheduler.get_jobs() if job.name == "bybit_history_update")
    fire_times = _next_fire_times(job, started_at, count=3)

    assert fire_times == [
        started_at,
        utc_datetime(2026, 1, 1, 1, 0, 5),
        utc_datetime(2026, 1, 1, 2, 0, 5),
    ]


@pytest.mark.asyncio
async def test_bootstrap_delays_history_backfill_by_five_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ensure_sections(_: SessionFactory, __: list[str]) -> None:
        return None

    started_at = utc_datetime(2026, 1, 1, 0, 3)
    monkeypatch.setattr("fundingpulse.tracker.bootstrap._ensure_sections", ensure_sections)
    monkeypatch.setattr("fundingpulse.tracker.bootstrap.utc_now", lambda: started_at)
    session_factory = cast(SessionFactory, object())

    scheduler = await bootstrap(
        session_factory=session_factory,
        exchanges=["bybit"],
    )

    job = next(job for job in scheduler.get_jobs() if job.name == "bybit_history_backfill")
    fire_times = _next_fire_times(job, started_at, count=3)

    assert fire_times == [
        utc_datetime(2026, 1, 1, 0, 8),
        utc_datetime(2026, 1, 1, 1, 5),
        utc_datetime(2026, 1, 1, 2, 5),
    ]


@pytest.mark.asyncio
async def test_bootstrap_registers_contract_registry_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ensure_sections(_: SessionFactory, __: list[str]) -> None:
        return None

    started_at = utc_datetime(2026, 1, 1)
    monkeypatch.setattr("fundingpulse.tracker.bootstrap._ensure_sections", ensure_sections)
    monkeypatch.setattr("fundingpulse.tracker.bootstrap.utc_now", lambda: started_at)
    session_factory = cast(SessionFactory, object())

    scheduler = await bootstrap(
        session_factory=session_factory,
        exchanges=[],
        registry_exchanges=["bybit"],
    )

    job = next(job for job in scheduler.get_jobs() if job.name == "bybit_contract_registry")
    fire_times = _next_fire_times(job, started_at, count=3)

    assert fire_times == [
        started_at,
        utc_datetime(2026, 1, 1, 0, 4),
        utc_datetime(2026, 1, 1, 0, 9),
    ]


@pytest.mark.asyncio
async def test_bootstrap_skips_singleton_jobs_for_non_owner_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ensure_sections(_: SessionFactory, __: list[str]) -> None:
        return None

    monkeypatch.setattr("fundingpulse.tracker.bootstrap._ensure_sections", ensure_sections)
    session_factory = cast(SessionFactory, object())

    scheduler = await bootstrap(
        session_factory=session_factory,
        exchanges=["bybit"],
        registry_exchanges=["okx"],
        owns_singleton_jobs=False,
    )

    jobs = {job.name for job in scheduler.get_jobs()}
    assert jobs == {"bybit_history_backfill", "bybit_history_update", "bybit_live"}


@pytest.mark.asyncio
async def test_bootstrap_seeds_sections_for_collection_and_registry_exchanges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded_sections: list[str] = []

    async def ensure_sections(_: SessionFactory, exchange_names: list[str]) -> None:
        seeded_sections.extend(exchange_names)

    monkeypatch.setattr("fundingpulse.tracker.bootstrap._ensure_sections", ensure_sections)
    session_factory = cast(SessionFactory, object())

    await bootstrap(
        session_factory=session_factory,
        exchanges=["bybit"],
        registry_exchanges=["okx"],
    )

    assert seeded_sections == ["bybit", "okx"]


def _next_fire_times(job: Job, started_at: UtcDateTime, *, count: int) -> list[UtcDateTime]:
    fire_times: list[UtcDateTime] = []
    previous_fire_time = None
    now = started_at
    for _ in range(count):
        next_fire_time = job.trigger.get_next_fire_time(previous_fire_time, now)
        assert next_fire_time is not None
        fire_times.append(next_fire_time)
        previous_fire_time = next_fire_time
        now = next_fire_time
    return fire_times
