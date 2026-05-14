"""Funding ingestion runtime configuration."""

from __future__ import annotations

from datetime import timedelta
from typing import Self

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fundingpulse.db_settings import DBSettings, DBTuningBase, db_tuning_config
from fundingpulse.exchange_selection import ExchangeSelectionSettings
from fundingpulse.ingestion.live.config import LiveEnqueuerConfig

load_dotenv()


class IngestionDBTuning(DBTuningBase):
    """SQLAlchemy engine/session overrides for ingestion services (FI_DB_*)."""

    model_config = db_tuning_config("FI_DB_")

    @model_validator(mode="after")
    def reject_expiring_sessions(self) -> Self:
        if self.session_kwargs.get("expire_on_commit") is not False:
            raise ValueError("Ingestion sessions must use expire_on_commit=False")
        return self


class IngestionLiveSettings(BaseSettings):
    """Live ingestion runtime knobs (FI_LIVE_*)."""

    model_config = SettingsConfigDict(
        env_prefix="FI_LIVE_",
        case_sensitive=False,
        extra="ignore",
    )

    enqueue_timeout_seconds: float = 45.0
    task_timeout_seconds: float = 45.0
    stale_running_grace_seconds: float = 15.0

    @field_validator(
        "enqueue_timeout_seconds",
        "task_timeout_seconds",
        "stale_running_grace_seconds",
    )
    @classmethod
    def reject_non_positive_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeout and grace settings must be greater than 0")
        return value

    def to_enqueuer_config(self) -> LiveEnqueuerConfig:
        return LiveEnqueuerConfig(
            enqueue_timeout=timedelta(seconds=self.enqueue_timeout_seconds),
            task_timeout=timedelta(seconds=self.task_timeout_seconds),
            stale_running_grace=timedelta(seconds=self.stale_running_grace_seconds),
        )


class Settings(BaseModel):
    """Top-level ingestion settings assembled by composition."""

    db: DBSettings
    db_tuning: IngestionDBTuning
    exchange_selection: ExchangeSelectionSettings
    live: IngestionLiveSettings


def build_settings() -> Settings:
    return Settings(
        db=DBSettings(),  # pyright: ignore[reportCallIssue]
        db_tuning=IngestionDBTuning(),
        exchange_selection=ExchangeSelectionSettings(),
        live=IngestionLiveSettings(),
    )
