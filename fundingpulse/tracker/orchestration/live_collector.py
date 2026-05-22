"""Snapshot current (unsettled) funding rates for every active contract.

Runs every minute per exchange. The exchange timestamp for a live rate is
the *next settlement time*, which stays fixed across the whole funding
window; we compute the sample timestamp ourselves from current time, so the
PK `(contract_id, timestamp)` is distinct per sample.

Error handling is permissive: a failed live snapshot is logged and swallowed
so the minute-cadence job never gets stuck — history ingestion is the
critical path, not live sampling.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from fundingpulse.db import SessionFactory
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.observability.logging import EventLogger, get_logger
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.observability import DomainEvents, Workflows
from fundingpulse.tracker.queries.contracts import get_active_by_section
from fundingpulse.tracker.queries.live_funding_points import insert_live_funding_points

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LiveCollectionResult:
    """Observable outcome of one tracker live funding collection."""

    expected_contracts: int
    received_rates: int
    written_points: int


async def collect_live(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    event_logger: EventLogger | None = None,
) -> LiveCollectionResult:
    """Fetch live rates for all active contracts and persist the snapshot."""
    log = (event_logger or logger).bind(workflow=Workflows.LIVE, exchange=section_name)
    started_at = monotonic()
    expected_contracts = 0
    received_rates = 0
    written_points = 0

    log.info(DomainEvents.LIVE_COLLECTION_STARTED)

    try:
        async with db() as session:
            contracts = list(await get_active_by_section(session, section_name))
        expected_contracts = len(contracts)
        if not contracts:
            result = LiveCollectionResult(
                expected_contracts=0,
                received_rates=0,
                written_points=0,
            )
            log.info(
                DomainEvents.LIVE_COLLECTION_COMPLETED,
                expected_contracts=result.expected_contracts,
                received_rates=result.received_rates,
                written_points=result.written_points,
                duration_seconds=monotonic() - started_at,
            )
            return result

        log.info(DomainEvents.LIVE_FETCH_STARTED, expected_contracts=expected_contracts)
        fetch_started_at = monotonic()
        rates = await adapter.fetch_live(contracts)
        received_rates = len(rates)
        log.info(
            DomainEvents.LIVE_FETCH_COMPLETED,
            expected_contracts=expected_contracts,
            received_rates=received_rates,
            fetch_duration_seconds=monotonic() - fetch_started_at,
        )

        records = [
            LiveFundingPoint(
                contract_id=contract_id,
                timestamp=rate.timestamp,
                funding_rate=rate.rate,
            )
            for contract_id, rate in rates.items()
        ]

        persist_started_at = monotonic()
        async with db.begin() as session:
            written_points = await insert_live_funding_points(session, records)

        log.info(
            DomainEvents.LIVE_PERSIST_COMPLETED,
            expected_contracts=expected_contracts,
            received_rates=received_rates,
            attempted_points=len(records),
            written_points=written_points,
            persist_duration_seconds=monotonic() - persist_started_at,
        )

        result = LiveCollectionResult(
            expected_contracts=expected_contracts,
            received_rates=received_rates,
            written_points=written_points,
        )
        log.info(
            DomainEvents.LIVE_COLLECTION_COMPLETED,
            expected_contracts=result.expected_contracts,
            received_rates=result.received_rates,
            written_points=result.written_points,
            duration_seconds=monotonic() - started_at,
        )
        return result
    except Exception as exc:
        log.exception(
            DomainEvents.LIVE_COLLECTION_FAILED,
            expected_contracts=expected_contracts,
            received_rates=received_rates,
            written_points=written_points,
            duration_seconds=monotonic() - started_at,
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=exc,
        )
        return LiveCollectionResult(
            expected_contracts=expected_contracts,
            received_rates=received_rates,
            written_points=written_points,
        )
