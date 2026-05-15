"""Live funding collection workflow for claimed ingestion tasks."""

from __future__ import annotations

from time import monotonic

from fundingpulse.db import SessionFactory
from fundingpulse.ingestion.exchanges.base import BaseLiveExchange
from fundingpulse.ingestion.live.constants import LIVE_FUNDING_PIPELINE
from fundingpulse.ingestion.live.dto import ClaimedLiveTask, LiveCollectionResult
from fundingpulse.ingestion.live.queries import (
    get_active_contracts_by_section,
    insert_live_funding_points,
)
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.observability.logging import EventLogger, get_logger
from fundingpulse.time import to_iso8601

logger = get_logger(__name__)


async def collect_live(
    *,
    adapter: BaseLiveExchange,
    task: ClaimedLiveTask,
    session_factory: SessionFactory,
    event_logger: EventLogger | None = None,
) -> LiveCollectionResult:
    """Fetch and persist one exchange-level live funding snapshot."""
    log = event_logger or logger
    async with session_factory() as session:
        contracts = list(await get_active_contracts_by_section(session, task.exchange))

    expected_contracts = len(contracts)
    if not contracts:
        _log_task_event(log, "live_fetch_completed", task=task, expected_contracts=0)
        return LiveCollectionResult(
            expected_contracts=0,
            received_rates=0,
            written_points=0,
        )

    _log_task_event(log, "live_fetch_started", task=task, expected_contracts=expected_contracts)
    started_at = monotonic()
    rates = await adapter.fetch_live(contracts)
    fetch_duration_seconds = monotonic() - started_at
    received_rates = len(rates)
    _log_task_event(
        log,
        "live_fetch_completed",
        task=task,
        expected_contracts=expected_contracts,
        received_rates=received_rates,
        fetch_duration_seconds=fetch_duration_seconds,
    )

    records = [
        LiveFundingPoint(
            contract_id=contract_id,
            timestamp=rate.timestamp,
            funding_rate=rate.rate,
        )
        for contract_id, rate in rates.items()
    ]
    started_at = monotonic()
    async with session_factory.begin() as session:
        written_points = await insert_live_funding_points(session, records)

    _log_task_event(
        log,
        "live_persist_completed",
        task=task,
        expected_contracts=expected_contracts,
        received_rates=received_rates,
        written_points=written_points,
        persist_duration_seconds=monotonic() - started_at,
    )
    return LiveCollectionResult(
        expected_contracts=expected_contracts,
        received_rates=received_rates,
        written_points=written_points,
    )


def _log_task_event(
    log: EventLogger,
    event: str,
    *,
    task: ClaimedLiveTask,
    **fields: object,
) -> None:
    log.info(
        event,
        pipeline=LIVE_FUNDING_PIPELINE,
        task_key=task.task_key,
        exchange=task.exchange,
        scheduled_for=to_iso8601(task.scheduled_for),
        worker_id=task.worker_id,
        **fields,
    )
