"""Funding tracker configuration.

Composition, not inheritance: each subsystem is its own BaseSettings with exactly
one env_prefix. The outer Settings is a plain BaseModel that wires them together.
See AGENTS.md (Configuration) for the rules behind this layout.
"""

from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from fundingpulse.db_settings import DBSettings

load_dotenv()


class TrackerDBTuning(BaseSettings):
    """SQLAlchemy engine/session overrides for the tracker (FT_DB_*)."""

    model_config = SettingsConfigDict(
        env_prefix="FT_DB_",
        case_sensitive=False,
        extra="ignore",
    )

    engine_kwargs: dict[str, Any] | None = None
    session_kwargs: dict[str, Any] | None = None


class TrackerAppSettings(BaseSettings):
    """Tracker-specific knobs (FT_*)."""

    model_config = SettingsConfigDict(
        env_prefix="FT_",
        case_sensitive=False,
        extra="ignore",
    )

    exchanges: str | None = None
    debug_exchanges: str | None = None
    debug_exchanges_live: str | None = None
    instance_id: int = 0
    total_instances: int = 1


class Settings(BaseModel):
    """Top-level tracker settings assembled by composition."""

    db: DBSettings
    db_tuning: TrackerDBTuning
    app: TrackerAppSettings


def build_settings() -> Settings:
    return Settings(
        db=DBSettings(),  # pyright: ignore[reportCallIssue]
        db_tuning=TrackerDBTuning(),
        app=TrackerAppSettings(),
    )
