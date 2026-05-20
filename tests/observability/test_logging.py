from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from typing import cast

import pytest
import structlog

from fundingpulse.observability.logging import configure_json_logging, get_logger


@pytest.fixture()
def restore_logging() -> Iterator[None]:
    root_logger = logging.getLogger()
    handlers = list(root_logger.handlers)
    level = root_logger.level
    try:
        yield
    finally:
        root_logger.handlers = handlers
        root_logger.setLevel(level)
        structlog.reset_defaults()


def test_configure_json_logging_renders_structlog_event(
    restore_logging: None,
) -> None:
    del restore_logging
    stream = io.StringIO()
    configure_json_logging(service="ingestion", component="live-worker", stream=stream)

    get_logger("fundingpulse.ingestion.live.worker").info(
        "live_task_completed",
        pipeline="live_funding",
        exchange="bybit",
        duration_seconds=1.25,
    )

    payload = _last_payload(stream)
    assert payload["event"] == "live_task_completed"
    assert payload["pipeline"] == "live_funding"
    assert payload["exchange"] == "bybit"
    assert payload["duration_seconds"] == 1.25
    assert payload["service"] == "ingestion"
    assert payload["component"] == "live-worker"
    assert payload["level"] == "info"
    assert payload["logger"] == "fundingpulse.ingestion.live.worker"
    assert cast(str, payload["timestamp"]).endswith("Z")


def test_bound_context_is_rendered_as_top_level_fields(
    restore_logging: None,
) -> None:
    del restore_logging
    stream = io.StringIO()
    configure_json_logging(service="ingestion", component="scheduler", stream=stream)

    get_logger("fundingpulse.ingestion.live.enqueuer").bind(
        pipeline="live_funding",
        scheduled_for="2026-05-08T12:34:00Z",
    ).info("live_enqueue_started")

    payload = _last_payload(stream)
    assert payload["event"] == "live_enqueue_started"
    assert payload["pipeline"] == "live_funding"
    assert payload["scheduled_for"] == "2026-05-08T12:34:00Z"
    assert payload["service"] == "ingestion"
    assert payload["component"] == "scheduler"


def test_runtime_fields_are_rendered_as_top_level_fields(
    restore_logging: None,
) -> None:
    del restore_logging
    stream = io.StringIO()
    configure_json_logging(
        service="tracker",
        component="scheduler",
        stream=stream,
        runtime_fields={"instance_id": 2, "total_instances": 4},
    )

    get_logger("fundingpulse.tracker.main").info("tracker_started")

    payload = _last_payload(stream)
    assert payload["event"] == "tracker_started"
    assert payload["service"] == "tracker"
    assert payload["component"] == "scheduler"
    assert payload["instance_id"] == 2
    assert payload["total_instances"] == 4


def test_configure_json_logging_renders_stdlib_logs_as_json(
    restore_logging: None,
) -> None:
    del restore_logging
    stream = io.StringIO()
    configure_json_logging(service="ingestion", component="scheduler", stream=stream)

    logging.getLogger("apscheduler").warning("scheduler warning")

    payload = _last_payload(stream)
    assert payload["event"] == "scheduler warning"
    assert payload["service"] == "ingestion"
    assert payload["component"] == "scheduler"
    assert payload["level"] == "warning"
    assert payload["logger"] == "apscheduler"


def test_configure_json_logging_renders_exception(
    restore_logging: None,
) -> None:
    del restore_logging
    stream = io.StringIO()
    configure_json_logging(service="ingestion", component="live-worker", stream=stream)

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        get_logger("fundingpulse.ingestion.live_worker_main").error(
            "ingestion_application_error",
            error_type="RuntimeError",
            error_message="boom",
            exc_info=True,
        )

    payload = _last_payload(stream)
    assert payload["event"] == "ingestion_application_error"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_message"] == "boom"
    assert "RuntimeError: boom" in cast(str, payload["exception"])


def _last_payload(stream: io.StringIO) -> dict[str, object]:
    line = stream.getvalue().splitlines()[-1]
    return cast(dict[str, object], json.loads(line))
