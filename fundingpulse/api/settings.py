"""Funding Data API configuration.

Each subsystem is its own BaseSettings with one env_prefix. Consumers use cached
providers instead of eager module-level instances, so importing the API surface
stays cheap and DB-free.
"""

from functools import lru_cache
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class APIDBTuning(BaseSettings):
    """SQLAlchemy engine/session overrides for the API (FDA_DB_*)."""

    model_config = SettingsConfigDict(
        env_prefix="FDA_DB_",
        case_sensitive=False,
        extra="ignore",
    )

    engine_kwargs: dict[str, Any] | None = None
    session_kwargs: dict[str, Any] | None = None


class CORSSettings(BaseSettings):
    """CORS middleware configuration (FDA_CORS_*).

    Every field is optional — None means fall back to middleware default.
    Use to_middleware_kwargs() to pass only explicitly set values.
    """

    model_config = SettingsConfigDict(
        env_prefix="FDA_CORS_",
        case_sensitive=False,
        extra="ignore",
    )

    allow_origins: list[str] | Literal["*"] | None = None
    allow_origin_regex: str | None = None
    allow_methods: list[str] | Literal["*"] | None = None
    allow_headers: list[str] | Literal["*"] | None = None
    allow_credentials: bool | None = None
    allow_private_network: bool | None = None
    expose_headers: list[str] | None = None
    max_age: int | None = None

    def to_middleware_kwargs(self) -> dict[str, object]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


@lru_cache
def get_api_db_tuning() -> APIDBTuning:
    return APIDBTuning()


@lru_cache
def get_cors_settings() -> CORSSettings:
    return CORSSettings()
