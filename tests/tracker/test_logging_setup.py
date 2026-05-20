from __future__ import annotations

import logging

import pytest

from fundingpulse.tracker import logging_setup


def test_configure_logging_sets_tracker_service_and_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def configure_json_logging(
        *,
        service: str,
        component: str,
        level: int,
        runtime_fields: dict[str, object] | None,
    ) -> None:
        calls.append(
            {
                "service": service,
                "component": component,
                "level": level,
                "runtime_fields": runtime_fields,
            }
        )

    monkeypatch.setattr(logging_setup, "configure_json_logging", configure_json_logging)

    logging_setup.configure_logging(instance_id=0, total_instances=1)

    assert calls == [
        {
            "service": "tracker",
            "component": "tracker",
            "level": logging.INFO,
            "runtime_fields": None,
        }
    ]


def test_configure_logging_sets_tracker_instance_runtime_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def configure_json_logging(
        *,
        service: str,
        component: str,
        level: int,
        runtime_fields: dict[str, object] | None,
    ) -> None:
        calls.append(
            {
                "service": service,
                "component": component,
                "level": level,
                "runtime_fields": runtime_fields,
            }
        )

    monkeypatch.setattr(logging_setup, "configure_json_logging", configure_json_logging)

    logging_setup.configure_logging(instance_id=2, total_instances=4)

    assert calls == [
        {
            "service": "tracker",
            "component": "tracker",
            "level": logging.INFO,
            "runtime_fields": {"instance_id": 2, "total_instances": 4},
        }
    ]


def test_configure_logging_keeps_noisy_loggers_at_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def configure_json_logging(
        *,
        service: str,
        component: str,
        level: int,
        runtime_fields: dict[str, object] | None,
    ) -> None:
        return None

    monkeypatch.setattr(logging_setup, "configure_json_logging", configure_json_logging)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
    logging.getLogger("apscheduler").setLevel(logging.DEBUG)

    logging_setup.configure_logging(instance_id=0, total_instances=1)

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("apscheduler").level == logging.WARNING
