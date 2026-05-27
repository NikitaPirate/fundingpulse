"""Shared persistence for settled historical funding points."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from fundingpulse.db import SessionFactory
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.time import UtcDateTime
from fundingpulse.tracker.exchanges.dto import FundingPoint
from fundingpulse.tracker.queries import contract_history_state
from fundingpulse.tracker.queries.funding_points import insert_historical_funding_points


@dataclass(frozen=True, slots=True)
class PersistedHistoricalBatch:
    """Committed historical batch metadata."""

    oldest_timestamp: UtcDateTime
    newest_timestamp: UtcDateTime
    points_written: int


async def persist_historical_funding_batch(
    db: SessionFactory,
    contract_id: UUID,
    points: Sequence[FundingPoint],
) -> PersistedHistoricalBatch:
    """Insert funding points and merge history bounds in one transaction."""
    if not points:
        raise ValueError("Cannot persist an empty historical funding batch")

    batch_oldest = min(point.timestamp for point in points)
    batch_newest = max(point.timestamp for point in points)
    records = [
        HistoricalFundingPoint(
            contract_id=contract_id,
            timestamp=point.timestamp,
            funding_rate=point.rate,
        )
        for point in points
    ]

    async with db.begin() as session:
        points_written = await insert_historical_funding_points(session, records)
        await contract_history_state.update_bounds(
            session,
            contract_id,
            oldest_timestamp=batch_oldest,
            newest_timestamp=batch_newest,
        )

    return PersistedHistoricalBatch(
        oldest_timestamp=batch_oldest,
        newest_timestamp=batch_newest,
        points_written=points_written,
    )
