"""Tracker-owned observability vocabulary."""

from __future__ import annotations

from enum import StrEnum


class Workflows(StrEnum):
    """Stable tracker workflows exposed as observability labels."""

    LIVE = "live"
    REGISTRY = "registry"


class DomainEvents(StrEnum):
    """Stable tracker events allowed to become Loki labels."""

    CONTRACT_REGISTRY_STARTED = "contract_registry_started"
    CONTRACT_REGISTRY_COMPLETED = "contract_registry_completed"
    CONTRACT_REGISTRY_FAILED = "contract_registry_failed"
    LIVE_COLLECTION_STARTED = "live_collection_started"
    LIVE_COLLECTION_COMPLETED = "live_collection_completed"
    LIVE_COLLECTION_FAILED = "live_collection_failed"
    LIVE_FETCH_STARTED = "live_fetch_started"
    LIVE_FETCH_COMPLETED = "live_fetch_completed"
    LIVE_PERSIST_COMPLETED = "live_persist_completed"


TRACKER_DOMAIN_EVENTS = frozenset(event.value for event in DomainEvents)
