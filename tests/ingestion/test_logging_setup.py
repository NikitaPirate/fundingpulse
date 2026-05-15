from __future__ import annotations

import logging

import pytest

from fundingpulse.ingestion import logging_setup


def test_configure_logging_sets_ingestion_service_and_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def configure_json_logging(*, service: str, component: str, level: int) -> None:
        calls.append(
            {
                "service": service,
                "component": component,
                "level": level,
            }
        )

    monkeypatch.setattr(logging_setup, "configure_json_logging", configure_json_logging)

    logging_setup.configure_logging(component="live-worker")

    assert calls == [
        {
            "service": "ingestion",
            "component": "live-worker",
            "level": logging.INFO,
        }
    ]
