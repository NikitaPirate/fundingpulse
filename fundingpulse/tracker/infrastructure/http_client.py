"""HTTP client with exponential backoff retry."""

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


@retry(**RETRY_CONFIG)
async def get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> JsonValue:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()


@retry(**RETRY_CONFIG)
async def post(
    url: str,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> JsonValue:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=json, headers=headers)
        response.raise_for_status()
        return response.json()
