"""Shared exchange selection settings and resolution."""

from collections.abc import Collection
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class ExchangeSelectionSettings(BaseSettings):
    """Shared exchange allowlist read from ENABLED_EXCHANGES."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    enabled_exchanges: tuple[str, ...] | None = None

    @field_validator("enabled_exchanges", mode="before")
    @classmethod
    def parse_enabled_exchanges(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_exchange_ids(value)
        return value


@dataclass(frozen=True, slots=True)
class ExchangeSelection:
    """Resolved exchange-selection input for a service-specific registry."""

    available_ids: Collection[str]
    requested_ids: Collection[str] | None = None
    source: str = "ENABLED_EXCHANGES"

    def resolve(self) -> list[str]:
        """Validate requested IDs against available IDs and return sorted IDs."""
        return resolve_enabled_exchanges(
            self.requested_ids,
            self.available_ids,
            source=self.source,
        )


def parse_exchange_ids(value: str | None) -> tuple[str, ...] | None:
    """Parse comma-separated exchange IDs using the shared env setting format."""
    if value is None:
        return None

    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or None


def resolve_enabled_exchanges(
    requested: Collection[str] | None,
    available: Collection[str],
    *,
    source: str,
) -> list[str]:
    """Resolve requested exchange IDs against a service-specific registry."""
    available_set = set(available)
    if requested is None:
        return sorted(available_set)

    seen: set[str] = set()
    duplicates: set[str] = set()
    for exchange in requested:
        if exchange in seen:
            duplicates.add(exchange)
        seen.add(exchange)
    if duplicates:
        raise ValueError(f"{source} contains duplicate exchange IDs: {sorted(duplicates)}")

    requested_set = seen
    unknown = requested_set - available_set
    if unknown:
        raise ValueError(
            f"{source} contains unknown exchange IDs: {sorted(unknown)}. "
            f"Available exchanges: {sorted(available_set)}"
        )

    return sorted(requested_set)
