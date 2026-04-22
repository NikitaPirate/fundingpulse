"""Historical funding point backfill and incremental updates.

Two entry points, both driven per-contract:

- sync: walk exchange history *backwards* in batches until the API returns
  empty. Exchanges page by `endTime`, so reverse pagination is the natural
  cursor. Each batch commits independently so crash recovery resumes from
  `ContractHistoryState.oldest_timestamp` on the next run.

- update: fetch points *after* the stored `newest_timestamp`. Skipped when
  less than one funding_interval has elapsed — keeps the hourly job from
  hammering the API for contracts that haven't produced a new point yet.

Both paths persist a batch and advance bounds in the same transaction via
`persist_batch`, which relies on `update_bounds`' SQL-level monotonic merge
(`LEAST`/`GREATEST`) to keep stored bounds safe against concurrent writes.

Sessions are opened and closed per DB operation — never held across HTTP
calls — so a slow exchange can't tie up a pool connection.

Timeouts differ by path: a full backfill may legitimately take many minutes
for a contract with years of history (the 10-minute ceiling is the
slowest-exchange worst case), while a per-run incremental update should be
effectively instant; the 1-minute ceiling is the safety net.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.exc import InvalidRequestError

from fundingpulse.db import SessionFactory
from fundingpulse.models.contract import Contract
from fundingpulse.models.contract_history_state import ContractHistoryState
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.time import UtcDateTime, utc_now
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.exchanges.dto import FundingPoint
from fundingpulse.tracker.orchestration.section_logger import SectionLogger
from fundingpulse.tracker.queries import contract_history_state
from fundingpulse.tracker.queries.contracts import get_active_by_section_with_history_state
from fundingpulse.tracker.queries.utils import bulk_insert

SYNC_TIMEOUT_SECONDS = 600.0
UPDATE_TIMEOUT_SECONDS = 60.0
PROGRESS_LOG_BATCH_INTERVAL = 10


@dataclass(slots=True)
class HistoryUpdateStats:
    contracts_total: int
    contracts_updated: int
    points_fetched: int


async def run_history_updates(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    logger: SectionLogger,
) -> HistoryUpdateStats:
    """Load active contracts and process each one concurrently."""
    async with db.begin() as session:
        contracts = list(await get_active_by_section_with_history_state(session, section_name))

    if not contracts:
        logger.warning("No contracts to process")
        return HistoryUpdateStats(0, 0, 0)

    logger.debug("Processing %d contracts", len(contracts))
    results = await process_contracts(
        adapter=adapter,
        contracts=contracts,
        db=db,
        logger=logger,
    )
    return HistoryUpdateStats(
        contracts_total=len(contracts),
        contracts_updated=sum(r[0] for r in results),
        points_fetched=sum(r[1] for r in results),
    )


async def process_contracts(
    *,
    adapter: BaseExchange,
    contracts: Sequence[Contract],
    db: SessionFactory,
    logger: SectionLogger,
) -> list[tuple[int, int]]:
    """Process all contracts in parallel, returning per-contract (updated, points).

    Exposed separately so tests can drive the sync/update loop with a
    preloaded contract list.
    """
    results: list[tuple[int, int]] = [(0, 0)] * len(contracts)
    tasks: list[tuple[int, asyncio.Task[tuple[int, int]]]] = []
    skipped = 0
    now = utc_now()

    for index, contract in enumerate(contracts):
        state = _require_history_state(contract)
        if _is_fresh_synced(contract, state, now):
            skipped += 1
            continue
        tasks.append(
            (index, asyncio.create_task(_process_one(adapter, contract, state, db, logger)))
        )

    if skipped:
        logger.debug("Skipped %d fresh history-synced contracts", skipped)

    if not tasks:
        return results

    task_results = await asyncio.gather(*(t for _, t in tasks), return_exceptions=True)
    for (index, _), result in zip(tasks, task_results, strict=True):
        results[index] = result if not isinstance(result, BaseException) else (0, 0)
    return results


async def _process_one(
    adapter: BaseExchange,
    contract: Contract,
    state: ContractHistoryState,
    db: SessionFactory,
    logger: SectionLogger,
) -> tuple[int, int]:
    """Run sync or update for one contract with a timeout and error isolation."""
    label = f"{contract.asset.name}/{contract.quote_name}"
    try:
        if not state.history_synced:
            async with asyncio.timeout(SYNC_TIMEOUT_SECONDS):
                points = await _sync(adapter, contract, state, db, logger)
        else:
            async with asyncio.timeout(UPDATE_TIMEOUT_SECONDS):
                points = await _update(adapter, contract, state, db, logger)
        return (1 if points > 0 else 0, points)
    except TimeoutError:
        op = "sync" if not state.history_synced else "update"
        ceiling = SYNC_TIMEOUT_SECONDS if not state.history_synced else UPDATE_TIMEOUT_SECONDS
        logger.warning("%s %s timed out after %ds", label, op, int(ceiling))
        return (0, 0)
    except Exception as e:
        logger.error("Failed to process %s: %s", label, e, exc_info=True)
        return (0, 0)


async def _sync(
    adapter: BaseExchange,
    contract: Contract,
    state: ContractHistoryState,
    db: SessionFactory,
    logger: SectionLogger,
) -> int:
    """Backfill full history by walking backwards until the API returns empty."""
    label = f"{contract.asset.name}/{contract.quote_name}"
    logger.debug("Starting sync for %s", label)

    total_points = 0
    batch_count = 0
    before_ts = state.oldest_timestamp - timedelta(seconds=1) if state.oldest_timestamp else None
    # True once any point — from this run OR a prior partial sync — is persisted.
    # Controls whether an empty response marks the contract synced or keeps it
    # open for the next hourly retry (see _finalize_sync_if_ready).
    has_stored_history = state.oldest_timestamp is not None

    while True:
        batch_count += 1
        logger.debug(
            "Sync batch #%d: %s — fetching before %s",
            batch_count,
            label,
            before_ts or "beginning",
        )

        points = await adapter.fetch_history_before(contract, before_ts)

        if not points:
            await _finalize_sync_if_ready(
                contract.id, has_stored_history, db, logger, label, batch_count, total_points
            )
            return total_points

        batch_oldest, batch_newest = await persist_batch(db, contract.id, points)
        total_points += len(points)
        has_stored_history = True
        before_ts = batch_oldest - timedelta(seconds=1)

        logger.debug(
            "Sync batch #%d: %s — %d points (oldest: %s, newest: %s)",
            batch_count,
            label,
            len(points),
            batch_oldest,
            batch_newest,
        )

        if batch_count % PROGRESS_LOG_BATCH_INTERVAL == 0:
            logger.info(
                "Sync progress for %s: batch #%d, %d total points, latest batch range %s to %s",
                label,
                batch_count,
                total_points,
                batch_oldest,
                batch_newest,
            )


async def _finalize_sync_if_ready(
    contract_id: UUID,
    has_stored_history: bool,
    db: SessionFactory,
    logger: SectionLogger,
    label: str,
    batch_count: int,
    total_points: int,
) -> None:
    """Mark history as synced, unless the contract has no points at all yet.

    A contract newly listed on the exchange may report zero history until its
    first funding settlement (hours away). We keep such contracts unsynced so
    the next hourly pass retries, instead of permanently skipping them.
    """
    if not has_stored_history:
        logger.debug("No history yet for %s; keeping history unsynced", label)
        return

    async with db.begin() as session:
        await contract_history_state.mark_history_synced(session, contract_id)
    logger.info(
        "No more history for %s, marking history synced (total batches: %d, total points: %d)",
        label,
        batch_count,
        total_points,
    )


async def _update(
    adapter: BaseExchange,
    contract: Contract,
    state: ContractHistoryState,
    db: SessionFactory,
    logger: SectionLogger,
) -> int:
    """Fetch points newer than the stored cursor, guarded by funding_interval."""
    label = f"{contract.asset.name}/{contract.quote_name}"
    newest_ts = _require_synced_newest_timestamp(contract, state)
    after_ts = newest_ts + timedelta(seconds=1)

    time_since_last = utc_now() - after_ts
    required_interval = timedelta(hours=contract.funding_interval)
    if time_since_last < required_interval:
        logger.debug(
            "Skipping update for %s, only %s passed (need %s)",
            label,
            time_since_last,
            required_interval,
        )
        return 0

    points = await adapter.fetch_history_after(contract, after_ts)
    if not points:
        return 0

    await persist_batch(db, contract.id, points)
    return len(points)


async def persist_batch(
    db: SessionFactory,
    contract_id: UUID,
    points: Sequence[FundingPoint],
) -> tuple[UtcDateTime, UtcDateTime]:
    """Insert funding points and merge bounds in one transaction.

    `update_bounds` does a SQL-level monotonic merge (LEAST/GREATEST), so it
    is always safe to pass both the batch's oldest and newest — existing
    bounds never shrink to a "worse" value.

    Returns (batch_oldest, batch_newest) so the caller can advance its
    pagination cursor.
    """
    batch_oldest = min(p.timestamp for p in points)
    batch_newest = max(p.timestamp for p in points)
    records = [
        HistoricalFundingPoint(
            contract_id=contract_id,
            timestamp=p.timestamp,
            funding_rate=p.rate,
        )
        for p in points
    ]

    async with db.begin() as session:
        await bulk_insert(session, HistoricalFundingPoint, records, on_conflict="ignore")
        await contract_history_state.update_bounds(
            session,
            contract_id,
            oldest_timestamp=batch_oldest,
            newest_timestamp=batch_newest,
        )

    return batch_oldest, batch_newest


def _require_history_state(contract: Contract) -> ContractHistoryState:
    """Fail loudly if the caller forgot to eager-load `history_state`.

    `Contract.history_state` uses `lazy="raise"` in the model, so callers must
    use `get_active_by_section_with_history_state` (or an equivalent selectin)
    to load the relationship up front.
    """
    try:
        state = contract.history_state
    except InvalidRequestError as e:
        raise RuntimeError(f"History state not loaded for contract {contract.id}") from e
    if state is None:
        raise RuntimeError(f"Missing history state for contract {contract.id}")
    return state


def _is_fresh_synced(
    contract: Contract,
    state: ContractHistoryState,
    now: UtcDateTime,
) -> bool:
    """True when a synced contract hasn't had time to produce a new point yet."""
    if not state.history_synced or state.newest_timestamp is None:
        return False
    after_ts = state.newest_timestamp + timedelta(seconds=1)
    return now - after_ts < timedelta(hours=contract.funding_interval)


def _require_synced_newest_timestamp(
    contract: Contract,
    state: ContractHistoryState,
) -> UtcDateTime:
    if state.newest_timestamp is None:
        raise RuntimeError(f"History-synced contract {contract.id} has no newest timestamp")
    return state.newest_timestamp
