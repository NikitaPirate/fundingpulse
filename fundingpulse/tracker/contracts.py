"""Tracker runtime contract models."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TrackedContract:
    """Persisted contract data needed outside the DB session."""

    id: UUID
    asset_name: str
    section_name: str
    quote_name: str
    funding_interval: int
