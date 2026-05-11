import pytest

from fundingpulse.api.settings import APIDBTuning
from fundingpulse.tracker.settings import TrackerDBTuning


def test_db_tuning_explicit_override_wins_over_default() -> None:
    tuning = APIDBTuning(engine_kwargs={"pool_size": 99})

    assert tuning.engine_kwargs["pool_size"] == 99


def test_db_tuning_unspecified_defaults_survive_merge() -> None:
    tuning = APIDBTuning(engine_kwargs={"pool_size": 99})

    assert "echo" in tuning.engine_kwargs
    assert "expire_on_commit" in tuning.session_kwargs


def test_service_db_tuning_env_namespaces_are_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDA_DB_ENGINE_KWARGS", '{"pool_size": 11}')
    monkeypatch.setenv("FT_DB_ENGINE_KWARGS", '{"pool_size": 22}')

    api_tuning = APIDBTuning()
    tracker_tuning = TrackerDBTuning()

    assert api_tuning.engine_kwargs["pool_size"] == 11
    assert tracker_tuning.engine_kwargs["pool_size"] == 22
