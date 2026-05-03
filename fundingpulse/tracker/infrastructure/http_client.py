"""HTTP client with exponential backoff retry and connection pooling."""

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# JSON can be any of these types
JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None

# Retry on errors: stop after 60s, exponential backoff (max 10s)
RETRY_CONFIG = {
    "retry": retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    "stop": stop_after_delay(60),
    "wait": wait_exponential(multiplier=1, max=10),
    "reraise": True,
}


class _HttpClient:
    """Module-level HTTP client container with connection pooling."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def startup(self, *, max_connections: int = 100) -> None:
        """Create shared httpx client. Call once at application startup."""
        if self._client is not None:
            raise RuntimeError("HTTP client already started")
        if max_connections < 1:
            raise ValueError("max_connections must be greater than 0")

        # Bugfix hot path: keep the shared process-wide client, but give it
        # enough active connection slots for all exchanges assigned to the
        # process. Replace with per-exchange clients/limits when tracker HTTP
        # concurrency is redesigned.
        limits = httpx.Limits(max_connections=max_connections)
        self._client = httpx.AsyncClient(timeout=30.0, limits=limits)
        logger.info("HTTP client started (max_connections=%s)", max_connections)

    async def shutdown(self) -> None:
        """Close shared httpx client. Safe to call if already closed."""
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None
        logger.info("HTTP client closed")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HTTP client not started — call startup() first")
        return self._client


_http = _HttpClient()

startup = _http.startup
shutdown = _http.shutdown


@retry(**RETRY_CONFIG)
async def get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> JsonValue:
    response = await _http.client.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


@retry(**RETRY_CONFIG)
async def post(
    url: str,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> JsonValue:
    response = await _http.client.post(url, json=json, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()
