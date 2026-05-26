"""Incrementally collect settled historical funding points.

This workflow is intentionally separate from historical backfill. It only moves
the newest bound forward by asking the exchange for points after the last stored
historical point, or from the start of the current hour for contracts with no
stored history yet.

The job owns a whole-run timeout. Per-contract failures are logged and isolated,
while a stuck exchange call lets APScheduler try again on the next hourly run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic

from fundingpulse.db import SessionFactory
from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.observability.logging import EventLogger, get_logger
from fundingpulse.time import UtcDateTime, start_of_hour, to_iso8601, utc_now
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import FundingPoint
from fundingpulse.tracker.observability import DomainEvents, Workflows
from fundingpulse.tracker.queries import contract_history_state
from fundingpulse.tracker.queries.contracts import (
    ContractWithHistoryState,
    get_contracts_with_history_state_by_section,
)
from fundingpulse.tracker.queries.funding_points import insert_historical_funding_points

HISTORY_UPDATE_TIMEOUT_SECONDS = 59 * 60

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HistoryUpdateResult:
    """Observable outcome of one incremental historical update."""

    contracts_total: int = 0
    contracts_skipped: int = 0
    contracts_attempted: int = 0
    contracts_updated: int = 0
    contracts_failed: int = 0
    points_fetched: int = 0
    points_written: int = 0


@dataclass(frozen=True, slots=True)
class _ContractUpdateResult:
    points_fetched: int = 0
    points_written: int = 0
    failed: bool = False


@dataclass(slots=True)
class _HistoryUpdateProgress:
    contracts_total: int = 0
    contracts_skipped: int = 0
    contracts_attempted: int = 0
    contracts_updated: int = 0
    contracts_failed: int = 0
    points_fetched: int = 0
    points_written: int = 0

    def apply(self, result: _ContractUpdateResult) -> None:
        self.contracts_updated += 1 if result.points_written > 0 else 0
        self.contracts_failed += 1 if result.failed else 0
        self.points_fetched += result.points_fetched
        self.points_written += result.points_written

    def snapshot(self) -> HistoryUpdateResult:
        return HistoryUpdateResult(
            contracts_total=self.contracts_total,
            contracts_skipped=self.contracts_skipped,
            contracts_attempted=self.contracts_attempted,
            contracts_updated=self.contracts_updated,
            contracts_failed=self.contracts_failed,
            points_fetched=self.points_fetched,
            points_written=self.points_written,
        )


async def run_history_update(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    event_logger: EventLogger | None = None,
    timeout_seconds: float = HISTORY_UPDATE_TIMEOUT_SECONDS,
) -> HistoryUpdateResult:
    """Scheduler-facing incremental history update with structured observability."""
    log = (event_logger or logger).bind(
        workflow=Workflows.HISTORY_UPDATE,
        exchange=section_name,
    )
    started_at = monotonic()
    progress = _HistoryUpdateProgress()

    log.info(DomainEvents.HISTORY_UPDATE_STARTED)

    try:
        async with asyncio.timeout(timeout_seconds):
            result = await _update_contracts(
                adapter=adapter,
                section_name=section_name,
                db=db,
                log=log,
                progress=progress,
            )
    except TimeoutError as exc:
        result = progress.snapshot()
        log.exception(
            DomainEvents.HISTORY_UPDATE_FAILED,
            **_result_fields(result),
            duration_seconds=monotonic() - started_at,
            timeout_seconds=timeout_seconds,
            error_type=type(exc).__name__,
            error_message=f"timed out after {timeout_seconds:g}s",
            exc_info=exc,
        )
        return result
    except Exception as exc:
        result = progress.snapshot()
        log.exception(
            DomainEvents.HISTORY_UPDATE_FAILED,
            **_result_fields(result),
            duration_seconds=monotonic() - started_at,
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=exc,
        )
        return result

    log.info(
        DomainEvents.HISTORY_UPDATE_COMPLETED,
        **_result_fields(result),
        duration_seconds=monotonic() - started_at,
    )
    return result


async def _update_contracts(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    log: EventLogger,
    progress: _HistoryUpdateProgress,
) -> HistoryUpdateResult:
    async with db() as session:
        contracts_with_states = list(
            await get_contracts_with_history_state_by_section(session, section_name)
        )

    if not contracts_with_states:
        return HistoryUpdateResult()

    now = utc_now()
    tasks: list[asyncio.Task[_ContractUpdateResult]] = []
    progress.contracts_total = len(contracts_with_states)

    for contract_with_state in contracts_with_states:
        if _is_fresh(contract_with_state.contract, contract_with_state.state, now):
            progress.contracts_skipped += 1
            continue

        tasks.append(
            asyncio.create_task(
                _update_one_contract(
                    adapter=adapter,
                    contract_state=contract_with_state,
                    db=db,
                    log=log,
                    now=now,
                )
            )
        )

    progress.contracts_attempted = len(tasks)
    try:
        for task in asyncio.as_completed(tasks):
            progress.apply(await task)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return progress.snapshot()


async def _update_one_contract(
    *,
    adapter: BaseExchange,
    contract_state: ContractWithHistoryState,
    db: SessionFactory,
    log: EventLogger,
    now: UtcDateTime,
) -> _ContractUpdateResult:
    contract = contract_state.contract
    after_timestamp = _next_fetch_timestamp(contract_state.state, now)

    try:
        points = await adapter.fetch_history_after(contract, after_timestamp)
        if not points:
            return _ContractUpdateResult()

        points_written = await _persist_points(db, contract, points)
        return _ContractUpdateResult(
            points_fetched=len(points),
            points_written=points_written,
        )
    except Exception as exc:
        log.exception(
            DomainEvents.HISTORY_UPDATE_CONTRACT_FAILED,
            contract_id=str(contract.id),
            asset=contract.asset_name,
            quote=contract.quote_name,
            after_timestamp=to_iso8601(after_timestamp),
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=exc,
        )
        return _ContractUpdateResult(failed=True)


async def _persist_points(
    db: SessionFactory,
    contract: Contract,
    points: Sequence[FundingPoint],
) -> int:
    batch_oldest = min(point.timestamp for point in points)
    batch_newest = max(point.timestamp for point in points)
    records = [
        HistoricalFundingPoint(
            contract_id=contract.id,
            timestamp=point.timestamp,
            funding_rate=point.rate,
        )
        for point in points
    ]

    async with db.begin() as session:
        points_written = await insert_historical_funding_points(session, records)
        await contract_history_state.update_bounds(
            session,
            contract.id,
            oldest_timestamp=batch_oldest,
            newest_timestamp=batch_newest,
        )
    return points_written


def _is_fresh(
    contract: Contract,
    state: ContractHistoryState,
    now: UtcDateTime,
) -> bool:
    if state.newest_timestamp is None:
        return False

    after_timestamp = state.newest_timestamp + timedelta(seconds=1)
    return now - after_timestamp < timedelta(hours=contract.funding_interval)


def _next_fetch_timestamp(
    state: ContractHistoryState,
    now: UtcDateTime,
) -> UtcDateTime:
    if state.newest_timestamp is None:
        return start_of_hour(now) - timedelta(seconds=1)
    return state.newest_timestamp + timedelta(seconds=1)


def _result_fields(result: HistoryUpdateResult) -> dict[str, object]:
    return {
        "contracts_total": result.contracts_total,
        "contracts_skipped": result.contracts_skipped,
        "contracts_attempted": result.contracts_attempted,
        "contracts_updated": result.contracts_updated,
        "contracts_failed": result.contracts_failed,
        "points_fetched": result.points_fetched,
        "points_written": result.points_written,
    }
