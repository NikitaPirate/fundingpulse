"""Backfill settled historical funding points.

This workflow is intentionally separate from incremental history updates. It
only works on contracts whose full historical range is not synced yet, walking
backward from the oldest stored point until the exchange returns no older data.

History update and backfill deliberately keep separate orchestration code:
their shapes currently match, but they encode different domain policies. Share
mechanics such as persistence, not the workflow state machine.

The job owns a whole-run timeout matching the hourly scheduler cadence. A stuck
exchange call is cancelled before the next run, while per-contract failures are
logged and isolated from the rest of the exchange.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from uuid import UUID

from fundingpulse.db import SessionFactory
from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.observability.logging import EventLogger, get_logger
from fundingpulse.time import UtcDateTime, to_iso8601
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.observability import DomainEvents, Workflows
from fundingpulse.tracker.orchestration.historical_persistence import (
    persist_historical_funding_batch,
)
from fundingpulse.tracker.queries import contract_history_state
from fundingpulse.tracker.queries.contracts import (
    ContractWithHistoryState,
    get_contracts_pending_history_backfill_by_section,
)

HISTORY_BACKFILL_TIMEOUT_SECONDS = 59 * 60

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class HistoryBackfillResult:
    """Observable outcome of one historical backfill run."""

    contracts_total: int = 0
    contracts_attempted: int = 0
    contracts_backfilled: int = 0
    contracts_failed: int = 0
    points_fetched: int = 0
    points_written: int = 0


@dataclass(frozen=True, slots=True)
class _ContractBackfillResult:
    points_fetched: int = 0
    points_written: int = 0
    backfilled: bool = False
    failed: bool = False


@dataclass(slots=True)
class _HistoryBackfillProgress:
    contracts_total: int = 0
    contracts_attempted: int = 0
    contracts_backfilled: int = 0
    contracts_failed: int = 0
    points_fetched: int = 0
    points_written: int = 0

    def apply(self, result: _ContractBackfillResult) -> None:
        self.contracts_backfilled += 1 if result.backfilled else 0
        self.contracts_failed += 1 if result.failed else 0
        self.points_fetched += result.points_fetched
        self.points_written += result.points_written

    def snapshot(self) -> HistoryBackfillResult:
        return HistoryBackfillResult(
            contracts_total=self.contracts_total,
            contracts_attempted=self.contracts_attempted,
            contracts_backfilled=self.contracts_backfilled,
            contracts_failed=self.contracts_failed,
            points_fetched=self.points_fetched,
            points_written=self.points_written,
        )


async def run_history_backfill(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    event_logger: EventLogger | None = None,
    timeout_seconds: float = HISTORY_BACKFILL_TIMEOUT_SECONDS,
) -> HistoryBackfillResult:
    """Scheduler-facing historical backfill with structured observability."""
    log = (event_logger or logger).bind(
        workflow=Workflows.HISTORY_BACKFILL,
        exchange=section_name,
    )
    started_at = monotonic()
    progress = _HistoryBackfillProgress()

    log.info(DomainEvents.HISTORY_BACKFILL_STARTED)

    try:
        async with asyncio.timeout(timeout_seconds):
            result = await _backfill_contracts(
                adapter=adapter,
                section_name=section_name,
                db=db,
                log=log,
                progress=progress,
            )
    except TimeoutError as exc:
        result = progress.snapshot()
        log.exception(
            DomainEvents.HISTORY_BACKFILL_FAILED,
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
            DomainEvents.HISTORY_BACKFILL_FAILED,
            **_result_fields(result),
            duration_seconds=monotonic() - started_at,
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=exc,
        )
        return result

    log.info(
        DomainEvents.HISTORY_BACKFILL_COMPLETED,
        **_result_fields(result),
        duration_seconds=monotonic() - started_at,
    )
    return result


async def _backfill_contracts(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    log: EventLogger,
    progress: _HistoryBackfillProgress,
) -> HistoryBackfillResult:
    async with db() as session:
        pending_backfills = list(
            await get_contracts_pending_history_backfill_by_section(session, section_name)
        )

    if not pending_backfills:
        return HistoryBackfillResult()

    tasks: list[asyncio.Task[_ContractBackfillResult]] = []
    progress.contracts_total = len(pending_backfills)

    for contract_with_state in pending_backfills:
        tasks.append(
            asyncio.create_task(
                _backfill_one_contract(
                    adapter=adapter,
                    contract_state=contract_with_state,
                    db=db,
                    log=log,
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


async def _backfill_one_contract(
    *,
    adapter: BaseExchange,
    contract_state: ContractWithHistoryState,
    db: SessionFactory,
    log: EventLogger,
) -> _ContractBackfillResult:
    contract = contract_state.contract
    state = contract_state.state
    before_timestamp = _initial_before_timestamp(state)

    try:
        return await _fetch_and_persist_backfill(
            adapter=adapter,
            contract=contract,
            state=state,
            db=db,
            before_timestamp=before_timestamp,
        )
    except Exception as exc:
        log.exception(
            DomainEvents.HISTORY_BACKFILL_CONTRACT_FAILED,
            contract_id=str(contract.id),
            asset=contract.asset_name,
            quote=contract.quote_name,
            before_timestamp=_timestamp_field(before_timestamp),
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=exc,
        )
        return _ContractBackfillResult(failed=True)


async def _fetch_and_persist_backfill(
    *,
    adapter: BaseExchange,
    contract: Contract,
    state: ContractHistoryState,
    db: SessionFactory,
    before_timestamp: UtcDateTime | None,
) -> _ContractBackfillResult:
    points_fetched = 0
    points_written = 0
    has_stored_history = state.oldest_timestamp is not None

    while True:
        points = await adapter.fetch_history_before(contract, before_timestamp)
        if not points:
            backfilled = await _mark_history_synced_if_ready(
                db,
                contract.id,
                has_stored_history=has_stored_history,
            )
            return _ContractBackfillResult(
                points_fetched=points_fetched,
                points_written=points_written,
                backfilled=backfilled,
            )

        batch = await persist_historical_funding_batch(db, contract.id, points)
        points_fetched += len(points)
        points_written += batch.points_written
        has_stored_history = True
        before_timestamp = batch.oldest_timestamp - timedelta(seconds=1)


async def _mark_history_synced_if_ready(
    db: SessionFactory,
    contract_id: UUID,
    *,
    has_stored_history: bool,
) -> bool:
    if not has_stored_history:
        return False

    async with db.begin() as session:
        await contract_history_state.mark_history_synced(session, contract_id)
    return True


def _initial_before_timestamp(state: ContractHistoryState) -> UtcDateTime | None:
    if state.oldest_timestamp is None:
        return None
    return state.oldest_timestamp - timedelta(seconds=1)


def _timestamp_field(value: UtcDateTime | None) -> str | None:
    if value is None:
        return None
    return to_iso8601(value)


def _result_fields(result: HistoryBackfillResult) -> dict[str, object]:
    return {
        "contracts_total": result.contracts_total,
        "contracts_attempted": result.contracts_attempted,
        "contracts_backfilled": result.contracts_backfilled,
        "contracts_failed": result.contracts_failed,
        "points_fetched": result.points_fetched,
        "points_written": result.points_written,
    }
