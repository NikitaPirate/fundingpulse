"""Environment-backed settings for funding tracker."""

from functools import cached_property
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from fundingpulse.settings import DBSettings


class FTDBSettings(DBSettings):
    """Funding tracker DB settings with service-specific kwargs."""

    engine_kwargs: dict[str, Any] | None = Field(default=None, alias="FT_ENGINE_KWARGS")
    session_kwargs: dict[str, Any] | None = Field(default=None, alias="FT_SESSION_KWARGS")


class Settings(BaseSettings):
    """Application settings loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug_exchanges: str | None = Field(default=None, alias="DEBUG_EXCHANGES")
    debug_exchanges_live: str | None = Field(default=None, alias="DEBUG_EXCHANGES_LIVE")
    exchanges: str | None = Field(default=None, alias="EXCHANGES")
    instance_id: int = Field(default=0, alias="INSTANCE_ID")
    total_instances: int = Field(default=1, alias="TOTAL_INSTANCES")

    @cached_property
    def db(self) -> FTDBSettings:
        return FTDBSettings()  # pyright: ignore[reportCallIssue]

    @property
    def db_connection(self) -> str:
        return self.db.connection_url
