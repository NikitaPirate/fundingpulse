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

from fundingpulse.db import SessionFactory
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.tracker.exchanges.base import BaseExchange
from fundingpulse.tracker.orchestration.section_logger import SectionLogger
from fundingpulse.tracker.queries.contracts import get_active_by_section
from fundingpulse.tracker.queries.utils import bulk_insert


async def collect_live(
    *,
    adapter: BaseExchange,
    section_name: str,
    db: SessionFactory,
    logger: SectionLogger,
) -> None:
    """Fetch live rates for all active contracts and persist the snapshot."""
    try:
        contracts = await _load_active_contracts(db, section_name)
        if not contracts:
            logger.warning("No active contracts for live collection")
            return

        logger.debug("Collecting live rates for %d contracts", len(contracts))
        rates = await adapter.fetch_live(list(contracts))
        if not rates:
            logger.warning("No live rates collected")
            return

        records = [
            LiveFundingPoint(
                contract_id=contract.id,
                timestamp=rate.timestamp,
                funding_rate=rate.rate,
            )
            for contract, rate in rates.items()
        ]

        async with db.begin() as session:
            await bulk_insert(session, LiveFundingPoint, records, on_conflict="ignore")

        _log_outcome(logger, success=len(records), expected=len(contracts))
    except Exception as e:
        logger.error("Failed to collect live rates: %s", e, exc_info=True)


async def _load_active_contracts(db: SessionFactory, section_name: str) -> list:
    async with db.begin() as session:
        return list(await get_active_by_section(session, section_name))


def _log_outcome(logger: SectionLogger, *, success: int, expected: int) -> None:
    failed = expected - success
    if failed:
        logger.info("Live collection: %d ok, %d failed", success, failed)
    else:
        logger.debug("Live collection: all %d rates collected", success)
