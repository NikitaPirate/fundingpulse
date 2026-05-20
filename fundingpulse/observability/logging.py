"""Structured logging setup shared across application runtimes."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Mapping
from typing import Protocol, TextIO, cast

import structlog
from structlog.typing import EventDict, WrappedLogger


class EventLogger(Protocol):
    """Event-oriented logger used by FundingPulse application code."""

    def bind(self, **fields: object) -> EventLogger: ...

    def debug(self, event: str, **fields: object) -> object: ...

    def info(self, event: str, **fields: object) -> object: ...

    def warning(self, event: str, **fields: object) -> object: ...

    def error(self, event: str, **fields: object) -> object: ...

    def exception(self, event: str, **fields: object) -> object: ...


Processor = Callable[[WrappedLogger, str, EventDict], EventDict]


def get_logger(name: str) -> EventLogger:
    """Return an event-oriented structured logger."""
    return cast(EventLogger, structlog.get_logger(name))


def configure_json_logging(
    *,
    service: str,
    component: str,
    level: int = logging.INFO,
    stream: TextIO | None = None,
    runtime_fields: Mapping[str, object] | None = None,
) -> None:
    """Configure stdlib and structlog to emit JSON application logs."""
    runtime_context = _add_runtime_context(
        service=service,
        component=component,
        runtime_fields=runtime_fields,
    )
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            runtime_context,
            # Runtime log timestamps are emitted in UTC, matching the rest of the application.
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)


def _add_runtime_context(
    *,
    service: str,
    component: str,
    runtime_fields: Mapping[str, object] | None = None,
) -> Processor:
    extra_fields = dict(runtime_fields or {})

    def add_runtime_context(
        logger: WrappedLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        del logger, method_name
        event_dict.update(extra_fields)
        event_dict["service"] = service
        event_dict["component"] = component
        return event_dict

    return add_runtime_context
