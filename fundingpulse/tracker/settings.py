"""Funding tracker configuration.

Composition, not inheritance: each subsystem is its own BaseSettings with exactly
one env_prefix. The outer Settings is a plain BaseModel that wires them together.
See AGENTS.md (Configuration) for the rules behind this layout.
"""

from typing import Self

from dotenv import load_dotenv
from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fundingpulse.db_settings import DBSettings, DBTuningBase, db_tuning_config
from fundingpulse.exchange_selection import ExchangeSelectionSettings

load_dotenv()


class TrackerDBTuning(DBTuningBase):
    """SQLAlchemy engine/session overrides for the tracker (FT_DB_*)."""

    model_config = db_tuning_config("FT_DB_")

    @model_validator(mode="after")
    def reject_expiring_sessions(self) -> Self:
        if self.session_kwargs.get("expire_on_commit") is not False:
            raise ValueError("Tracker sessions must use expire_on_commit=False")
        return self


class TrackerAppSettings(BaseSettings):
    """Tracker-specific knobs (FT_*)."""

    model_config = SettingsConfigDict(
        env_prefix="FT_",
        case_sensitive=False,
        extra="ignore",
    )

    debug_exchanges: str | None = None
    debug_exchanges_live: str | None = None
    instance_id: int = 0
    total_instances: int = 1


class Settings(BaseModel):
    """Top-level tracker settings assembled by composition."""

    db: DBSettings
    db_tuning: TrackerDBTuning
    exchange_selection: ExchangeSelectionSettings
    app: TrackerAppSettings


def build_settings() -> Settings:
    return Settings(
        db=DBSettings(),  # pyright: ignore[reportCallIssue]
        db_tuning=TrackerDBTuning(),
        exchange_selection=ExchangeSelectionSettings(),
        app=TrackerAppSettings(),
    )
