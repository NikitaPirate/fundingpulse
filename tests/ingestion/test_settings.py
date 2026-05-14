from __future__ import annotations

import pytest

from fundingpulse.ingestion.settings import IngestionDBTuning, IngestionLiveSettings


def test_ingestion_live_settings_use_fi_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FI_LIVE_ENQUEUE_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("FI_LIVE_TASK_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("FI_LIVE_STALE_RUNNING_GRACE_SECONDS", "5")

    config = IngestionLiveSettings().to_enqueuer_config()

    assert config.enqueue_timeout.total_seconds() == 10
    assert config.task_timeout.total_seconds() == 20
    assert config.stale_running_grace.total_seconds() == 5


def test_ingestion_db_tuning_rejects_expiring_sessions() -> None:
    with pytest.raises(ValueError, match="expire_on_commit=False"):
        IngestionDBTuning(session_kwargs={"expire_on_commit": True})
