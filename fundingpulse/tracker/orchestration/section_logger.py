"""Logger adapter that prepends [section] prefix to every message."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any


class SectionLogger(logging.LoggerAdapter):  # type: ignore[type-arg]
    """Prepends `[section] ` to each log record.

    Centralises the prefix that was previously duplicated in every
    f-string across the orchestration layer.
    """

    def __init__(self, logger: logging.Logger, section: str) -> None:
        super().__init__(logger, {"section": section})
        self._section = section

    def process(
        self, msg: object, kwargs: MutableMapping[str, Any]
    ) -> tuple[object, MutableMapping[str, Any]]:
        return f"[{self._section}] {msg}", kwargs


def make_section_logger(name: str, section: str) -> SectionLogger:
    return SectionLogger(logging.getLogger(name), section)
