"""Base response wrappers for API endpoints."""

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse[T](BaseModel):
    data: T
    meta: dict[str, object] | None = None
