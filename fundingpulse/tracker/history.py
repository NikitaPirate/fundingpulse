"""Tracker history-state projections."""

from __future__ import annotations

from dataclasses import dataclass

from fundingpulse.time import UtcDateTime


@dataclass(frozen=True, slots=True)
class ContractHistoryStateSnapshot:
    """Read-only subset of ContractHistoryState used outside the DB session."""

    history_synced: bool
    oldest_timestamp: UtcDateTime | None
    newest_timestamp: UtcDateTime | None
