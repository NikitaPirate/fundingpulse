from __future__ import annotations

import pytest

from fundingpulse.exchange_selection import (
    ExchangeSelectionSettings,
    parse_exchange_ids,
    resolve_enabled_exchanges,
)


def test_exchange_selection_settings_parse_comma_separated_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLED_EXCHANGES", "bybit, okx")

    settings = ExchangeSelectionSettings()

    assert settings.enabled_exchanges == ("bybit", "okx")


def test_parse_exchange_ids_treats_empty_selection_as_all() -> None:
    assert parse_exchange_ids(" , ") is None


def test_exchange_selection_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate exchange IDs"):
        resolve_enabled_exchanges(
            parse_exchange_ids("bybit,bybit"),
            {"bybit", "okx"},
            source="ENABLED_EXCHANGES",
        )


def test_resolve_enabled_exchanges_rejects_unknown_ids() -> None:
    with pytest.raises(ValueError, match="ENABLED_EXCHANGES contains unknown exchange IDs"):
        resolve_enabled_exchanges(
            ("bybit", "missing"),
            {"bybit", "okx"},
            source="ENABLED_EXCHANGES",
        )


def test_resolve_enabled_exchanges_defaults_to_all_available() -> None:
    assert resolve_enabled_exchanges(None, {"okx", "bybit"}, source="ENABLED_EXCHANGES") == [
        "bybit",
        "okx",
    ]
