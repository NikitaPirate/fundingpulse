"""Shared database connection settings (DB_* env namespace)."""

from dotenv import load_dotenv
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
