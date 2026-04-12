"""Shared fixtures for tracker tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from fundingpulse.tracker.infrastructure import http_client

MockHttp = Callable[..., tuple["HttpCallRecorder", "HttpCallRecorder"]]


class HttpCallRecorder:
    """Replays HTTP responses in call order. Raises on unexpected extra calls."""

    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def __call__(self, url: str, **kwargs: object) -> object:
        if self._index >= len(self._responses):
            raise RuntimeError(
                f"HTTP mock exhausted after {len(self._responses)} call(s). Extra call to {url!r}"
            )
        response = self._responses[self._index]
        self._index += 1
        return response

    @property
    def call_count(self) -> int:
        return self._index


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> MockHttp:
    """Patch http_client.get and http_client.post with ordered call recorders.

    Usage::

        def test_something(mock_http):
            mock_http(get_responses=[...], post_responses=[...])
            result = await adapter.get_contracts()
    """

    def _setup(
        get_responses: list[object] | None = None,
        post_responses: list[object] | None = None,
    ) -> tuple[HttpCallRecorder, HttpCallRecorder]:
        get_recorder = HttpCallRecorder(get_responses or [])
        post_recorder = HttpCallRecorder(post_responses or [])
        monkeypatch.setattr(http_client, "get", get_recorder)
        monkeypatch.setattr(http_client, "post", post_recorder)
        return get_recorder, post_recorder

    return _setup
