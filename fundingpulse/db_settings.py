"""Shared database connection settings (DB_* env namespace)."""

from typing import Any, ClassVar, Self

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

load_dotenv()


class DBSettings(BaseSettings):
    """Database credentials shared across services.

    Used via composition, never subclassed — a child env_prefix would re-prefix
    inherited fields and break the single source of truth for DB_*.
    """

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        extra="ignore",
    )

    host: str
    port: int
    user: str
    password: str
    dbname: str

    @property
    def connection_url(self) -> str:
        return URL.create(
            "timescaledb+psycopg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.dbname,
        ).render_as_string(hide_password=False)


class DBTuningBase(BaseSettings):
    """Base for service-specific SQLAlchemy tuning settings.

    Subclasses own their env_prefix. The base owns common defaults and partial
    override merge behavior.
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    default_engine_kwargs: ClassVar[dict[str, Any]] = {
        "echo": False,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }
    default_session_kwargs: ClassVar[dict[str, Any]] = {
        "expire_on_commit": False,
    }

    engine_kwargs: dict[str, Any] = Field(default_factory=dict)
    session_kwargs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def apply_defaults(self) -> Self:
        self.engine_kwargs = {**type(self).default_engine_kwargs, **self.engine_kwargs}
        self.session_kwargs = {**type(self).default_session_kwargs, **self.session_kwargs}
        return self


def db_tuning_config(env_prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=env_prefix,
        case_sensitive=False,
        extra="ignore",
    )
