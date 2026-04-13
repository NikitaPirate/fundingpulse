"""Tests for fundingpulse/tracker/db/utils.py::bulk_insert.

Tests PostgreSQL-specific conflict handling (DO NOTHING / DO UPDATE SET),
chunked inserts, and edge cases. Uses real TimescaleDB via testcontainers.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.models.asset import Asset
from fundingpulse.models.contract import Contract
from fundingpulse.models.historical_funding_point import HistoricalFundingPoint
from fundingpulse.models.live_funding_point import LiveFundingPoint
from fundingpulse.testing.helpers.data_helpers import get_or_create_asset, get_or_create_section
from fundingpulse.time import utc_now
from fundingpulse.tracker.db.utils import bulk_insert


async def _mk_deps(session: AsyncSession, asset: str, section: str) -> None:
    await get_or_create_asset(session, asset)
    await get_or_create_section(session, section)


def _assert_aware_utc_timestamp(value: object) -> None:
    assert hasattr(value, "tzinfo")
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_basic_insert(db_session: AsyncSession) -> None:
    """Records are inserted and queryable."""
    await _mk_deps(db_session, "BTC", "test_ex")
    records = [
        Contract(asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=8)
    ]

    await bulk_insert(db_session, Contract, records)
    await db_session.commit()

    result = await db_session.execute(select(Contract))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].asset_name == "BTC"
    assert rows[0].funding_interval == 8


@pytest.mark.asyncio
async def test_empty_list_is_noop(db_session: AsyncSession) -> None:
    """Empty list is a no-op — no error, nothing inserted."""
    await bulk_insert(db_session, Contract, [])

    result = await db_session.execute(select(Contract))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_on_conflict_ignore_skips_duplicates(db_session: AsyncSession) -> None:
    """Duplicate records are silently skipped; original data is preserved."""
    await _mk_deps(db_session, "BTC", "test_ex")

    original = Contract(
        asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=8
    )
    await bulk_insert(db_session, Contract, [original], on_conflict="ignore")
    await db_session.commit()

    duplicate = Contract(
        asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=4
    )
    await bulk_insert(db_session, Contract, [duplicate], on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(select(Contract))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].funding_interval == 8  # original value preserved


@pytest.mark.asyncio
async def test_on_conflict_update_modifies_specified_fields(db_session: AsyncSession) -> None:
    """On conflict, only fields listed in update_fields are changed."""
    await _mk_deps(db_session, "BTC", "test_ex")

    original = Contract(
        asset_name="BTC",
        section_name="test_ex",
        quote_name="USDT",
        funding_interval=8,
        deprecated=False,
    )
    await bulk_insert(db_session, Contract, [original], on_conflict="ignore")
    await db_session.commit()

    updated = Contract(
        asset_name="BTC",
        section_name="test_ex",
        quote_name="USDT",
        funding_interval=4,
        deprecated=True,
    )
    await bulk_insert(
        db_session,
        Contract,
        [updated],
        conflict_target=["asset_name", "section_name", "quote_name"],
        on_conflict="update",
        update_fields=["funding_interval", "deprecated"],
    )
    await db_session.commit()

    result = await db_session.execute(select(Contract))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].funding_interval == 4
    assert rows[0].deprecated is True


@pytest.mark.asyncio
async def test_on_conflict_update_leaves_other_fields_unchanged(db_session: AsyncSession) -> None:
    """Fields not in update_fields stay at their original values on conflict."""
    await _mk_deps(db_session, "BTC", "test_ex")

    original = Contract(
        asset_name="BTC",
        section_name="test_ex",
        quote_name="USDT",
        funding_interval=8,
        synced=True,
    )
    await bulk_insert(db_session, Contract, [original], on_conflict="ignore")
    await db_session.commit()

    upsert = Contract(
        asset_name="BTC",
        section_name="test_ex",
        quote_name="USDT",
        funding_interval=4,
        synced=False,
    )
    await bulk_insert(
        db_session,
        Contract,
        [upsert],
        conflict_target=["asset_name", "section_name", "quote_name"],
        on_conflict="update",
        update_fields=["funding_interval"],  # synced NOT listed
    )
    await db_session.commit()

    result = await db_session.execute(select(Contract))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].funding_interval == 4  # updated
    assert rows[0].synced is True  # unchanged


@pytest.mark.asyncio
async def test_on_conflict_update_requires_conflict_target(db_session: AsyncSession) -> None:
    """ValueError raised when on_conflict='update' but conflict_target is missing."""
    await _mk_deps(db_session, "BTC", "test_ex")
    records = [
        Contract(asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=8)
    ]

    with pytest.raises(ValueError, match="conflict_target and update_fields"):
        await bulk_insert(
            db_session,
            Contract,
            records,
            on_conflict="update",
            update_fields=["funding_interval"],
        )


@pytest.mark.asyncio
async def test_on_conflict_update_requires_update_fields(db_session: AsyncSession) -> None:
    """ValueError raised when on_conflict='update' but update_fields is missing."""
    await _mk_deps(db_session, "BTC", "test_ex")
    records = [
        Contract(asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=8)
    ]

    with pytest.raises(ValueError, match="conflict_target and update_fields"):
        await bulk_insert(
            db_session,
            Contract,
            records,
            conflict_target=["asset_name", "section_name", "quote_name"],
            on_conflict="update",
        )


@pytest.mark.asyncio
async def test_chunking_inserts_all_records(db_session: AsyncSession) -> None:
    """1500 records with chunk_size=1000 are all inserted without data loss."""
    n = 1500
    assets = [Asset(name=f"ASSET_{i:04d}") for i in range(n)]
    await bulk_insert(db_session, Asset, assets, on_conflict="ignore")
    await get_or_create_section(db_session, "bulk_ex")
    await db_session.commit()

    contracts = [
        Contract(
            asset_name=f"ASSET_{i:04d}",
            section_name="bulk_ex",
            quote_name="USDT",
            funding_interval=8,
        )
        for i in range(n)
    ]
    await bulk_insert(db_session, Contract, contracts, chunk_size=1000, on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(select(Contract))
    assert len(result.scalars().all()) == n


@pytest.mark.asyncio
async def test_partial_duplicates_with_ignore(db_session: AsyncSession) -> None:
    """Mix of new and existing records: existing unchanged, new inserted."""
    for sym in ["BTC", "ETH", "SOL"]:
        await get_or_create_asset(db_session, sym)
    await get_or_create_section(db_session, "test_ex")

    existing = [
        Contract(asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=8),
        Contract(asset_name="ETH", section_name="test_ex", quote_name="USDT", funding_interval=8),
    ]
    await bulk_insert(db_session, Contract, existing, on_conflict="ignore")
    await db_session.commit()

    mixed = [
        Contract(
            asset_name="BTC", section_name="test_ex", quote_name="USDT", funding_interval=4
        ),  # duplicate — should be ignored
        Contract(
            asset_name="SOL", section_name="test_ex", quote_name="USDT", funding_interval=1
        ),  # new — should be inserted
    ]
    await bulk_insert(db_session, Contract, mixed, on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(select(Contract).order_by(Contract.asset_name))
    rows = result.scalars().all()
    by_asset = {r.asset_name: r for r in rows}

    assert len(rows) == 3
    assert by_asset["BTC"].funding_interval == 8  # original preserved
    assert by_asset["ETH"].funding_interval == 8  # untouched
    assert by_asset["SOL"].funding_interval == 1  # new record inserted


@pytest.mark.asyncio
async def test_historical_funding_point_round_trip_keeps_aware_utc(
    db_session: AsyncSession,
) -> None:
    await _mk_deps(db_session, "BTC", "time_ex")

    contract = Contract(
        asset_name="BTC",
        section_name="time_ex",
        quote_name="USDT",
        funding_interval=8,
    )
    await bulk_insert(db_session, Contract, [contract], on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(
        select(Contract).where(Contract.asset_name == "BTC", Contract.section_name == "time_ex")
    )
    persisted_contract = result.scalar_one()

    record = HistoricalFundingPoint(
        contract_id=persisted_contract.id,
        timestamp=utc_now(),
        funding_rate=0.001,
    )
    await bulk_insert(db_session, HistoricalFundingPoint, [record], on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(select(HistoricalFundingPoint))
    persisted_record = result.scalar_one()
    _assert_aware_utc_timestamp(persisted_record.timestamp)


@pytest.mark.asyncio
async def test_live_funding_point_round_trip_keeps_aware_utc(
    db_session: AsyncSession,
) -> None:
    await _mk_deps(db_session, "ETH", "time_ex_live")

    contract = Contract(
        asset_name="ETH",
        section_name="time_ex_live",
        quote_name="USDT",
        funding_interval=8,
    )
    await bulk_insert(db_session, Contract, [contract], on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(
        select(Contract).where(
            Contract.asset_name == "ETH",
            Contract.section_name == "time_ex_live",
        )
    )
    persisted_contract = result.scalar_one()

    record = LiveFundingPoint(
        contract_id=persisted_contract.id,
        timestamp=utc_now(),
        funding_rate=0.002,
    )
    await bulk_insert(db_session, LiveFundingPoint, [record], on_conflict="ignore")
    await db_session.commit()

    result = await db_session.execute(select(LiveFundingPoint))
    persisted_record = result.scalar_one()
    _assert_aware_utc_timestamp(persisted_record.timestamp)
