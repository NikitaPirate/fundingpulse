"""Queries for funding data endpoints."""

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fundingpulse.api.dto.enums import NormalizeToInterval
from fundingpulse.api.dto.funding_data import (
    CumulativeFundingDifference,
    FundingPeriodSums,
    FundingPoint,
    FundingRateDifference,
    FundingWallAsset,
    FundingWallResponse,
    HistoricalAvgEntry,
    HistoricalAvgWindow,
    LatestFundingPoint,
    PaginatedCumulativeFundingDifference,
    PaginatedFundingRateDifference,
)
from fundingpulse.api.queries.funding_sql_composer import FundingQueryComposer
from fundingpulse.time import from_unix_seconds, to_unix_seconds, utc_now


def _paginate_funding_rate(
    rows: Sequence[Mapping[Any, Any]],
    offset: int | None,
    limit: int | None,
) -> PaginatedFundingRateDifference:
    total_count = rows[0]["total_count"] if rows else 0
    data = [
        FundingRateDifference.model_validate({k: v for k, v in row.items() if k != "total_count"})
        for row in rows
    ]
    return PaginatedFundingRateDifference(
        data=data,
        total_count=total_count,
        offset=offset or 0,
        limit=limit or len(data),
        has_more=(offset or 0) + len(data) < total_count,
    )


def _paginate_cumulative(
    rows: Sequence[Mapping[Any, Any]],
    offset: int | None,
    limit: int | None,
) -> PaginatedCumulativeFundingDifference:
    total_count = rows[0]["total_count"] if rows else 0
    data = [
        CumulativeFundingDifference.model_validate(
            {k: v for k, v in row.items() if k != "total_count"}
        )
        for row in rows
    ]
    return PaginatedCumulativeFundingDifference(
        data=data,
        total_count=total_count,
        offset=offset or 0,
        limit=limit or len(data),
        has_more=(offset or 0) + len(data) < total_count,
    )


async def calculate_normalization_multiplier(
    session: AsyncSession,
    contract_id: UUID,
    normalize_to_interval: NormalizeToInterval,
) -> float:
    if normalize_to_interval == NormalizeToInterval.RAW:
        return 1.0

    result = await session.execute(
        text("SELECT funding_interval FROM contract WHERE id = :contract_id"),
        {"contract_id": contract_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError(f"Contract with id {contract_id} not found for normalization.")

    funding_interval = row["funding_interval"]
    if funding_interval and funding_interval > 0:
        interval_value = normalize_to_interval.value
        unit = interval_value[-1]
        amount = float(interval_value[:-1])
        target_hours = amount if unit == "h" else amount * 24
        return target_hours / funding_interval

    return 1.0


async def get_historical_points(
    session: AsyncSession,
    contract_id: UUID,
    from_ts: int,
    to_ts: int,
    normalize_to_interval: NormalizeToInterval = NormalizeToInterval.RAW,
) -> Sequence[FundingPoint]:
    multiplier = await calculate_normalization_multiplier(
        session, contract_id, normalize_to_interval
    )

    result = await session.execute(
        text(
            """
            SELECT
                EXTRACT(EPOCH FROM timestamp)::bigint AS timestamp,
                (funding_rate * :multiplier) AS funding_rate,
                contract_id
            FROM historical_funding_point
            WHERE contract_id = :contract_id
              AND timestamp >= to_timestamp(:from_ts)
              AND timestamp <= to_timestamp(:to_ts)
            ORDER BY timestamp ASC
            """
        ),
        {
            "contract_id": contract_id,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "multiplier": multiplier,
        },
    )

    return [FundingPoint.model_validate(row) for row in result.mappings().all()]


async def get_aggregated_live_points(
    session: AsyncSession,
    contract_id: UUID,
    from_ts: int,
    to_ts: int,
    normalize_to_interval: NormalizeToInterval = NormalizeToInterval.RAW,
) -> Sequence[FundingPoint]:
    multiplier = await calculate_normalization_multiplier(
        session, contract_id, normalize_to_interval
    )

    result = await session.execute(
        text(
            """
            SELECT
                EXTRACT(EPOCH FROM bucket)::bigint AS timestamp,
                (avg_funding_rate * :multiplier) AS funding_rate,
                contract_id
            FROM lfp_smart
            WHERE contract_id = :contract_id
              AND bucket BETWEEN to_timestamp(:from_ts) AND to_timestamp(:to_ts)
            ORDER BY bucket ASC
            """
        ),
        {
            "contract_id": contract_id,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "multiplier": multiplier,
        },
    )

    return [FundingPoint.model_validate(row) for row in result.mappings().all()]


async def get_funding_period_sums(
    session: AsyncSession,
    contract_id: UUID,
) -> FundingPeriodSums:
    result = await session.execute(
        text(
            """
            WITH period_data AS (
                SELECT
                    c.id AS contract_id,
                    c.asset_name,
                    s.name AS section_name,
                    c.quote_name,
                    c.funding_interval,
                    hfp.funding_rate,
                    hfp.timestamp,
                    CASE WHEN hfp.timestamp >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END AS within_7d,
                    CASE WHEN hfp.timestamp >= NOW() - INTERVAL '14 days' THEN 1 ELSE 0 END AS within_14d,
                    CASE WHEN hfp.timestamp >= NOW() - INTERVAL '30 days' THEN 1 ELSE 0 END AS within_30d,
                    CASE WHEN hfp.timestamp >= NOW() - INTERVAL '90 days' THEN 1 ELSE 0 END AS within_90d,
                    CASE WHEN hfp.timestamp >= NOW() - INTERVAL '180 days' THEN 1 ELSE 0 END AS within_180d,
                    CASE WHEN hfp.timestamp >= NOW() - INTERVAL '365 days' THEN 1 ELSE 0 END AS within_365d
                FROM contract c
                JOIN section s ON c.section_name = s.name
                LEFT JOIN historical_funding_point hfp ON c.id = hfp.contract_id
                    AND hfp.timestamp >= NOW() - INTERVAL '365 days'
                WHERE c.id = :contract_id AND c.deprecated = false
            ),
            period_sums AS (
                SELECT
                    pd.contract_id,
                    pd.asset_name,
                    pd.section_name,
                    pd.quote_name,
                    pd.funding_interval,
                    SUM(CASE WHEN pd.within_7d = 1 THEN pd.funding_rate ELSE 0 END) AS sum_7d_raw,
                    SUM(CASE WHEN pd.within_14d = 1 THEN pd.funding_rate ELSE 0 END) AS sum_14d_raw,
                    SUM(CASE WHEN pd.within_30d = 1 THEN pd.funding_rate ELSE 0 END) AS sum_30d_raw,
                    SUM(CASE WHEN pd.within_90d = 1 THEN pd.funding_rate ELSE 0 END) AS sum_90d_raw,
                    SUM(CASE WHEN pd.within_180d = 1 THEN pd.funding_rate ELSE 0 END) AS sum_180d_raw,
                    SUM(CASE WHEN pd.within_365d = 1 THEN pd.funding_rate ELSE 0 END) AS sum_365d_raw,
                    SUM(pd.within_7d) AS count_7d,
                    SUM(pd.within_14d) AS count_14d,
                    SUM(pd.within_30d) AS count_30d,
                    SUM(pd.within_90d) AS count_90d,
                    SUM(pd.within_180d) AS count_180d,
                    SUM(pd.within_365d) AS count_365d,
                    (24.0 * 7 / pd.funding_interval) AS expected_7d,
                    (24.0 * 14 / pd.funding_interval) AS expected_14d,
                    (24.0 * 30 / pd.funding_interval) AS expected_30d,
                    (24.0 * 90 / pd.funding_interval) AS expected_90d,
                    (24.0 * 180 / pd.funding_interval) AS expected_180d,
                    (24.0 * 365 / pd.funding_interval) AS expected_365d
                FROM period_data pd
                GROUP BY pd.contract_id, pd.asset_name, pd.section_name, pd.quote_name, pd.funding_interval
            )
            SELECT
                ps.contract_id,
                ps.asset_name,
                ps.section_name,
                ps.quote_name,
                CASE WHEN ps.count_7d >= ps.expected_7d * 0.98 THEN ps.sum_7d_raw ELSE NULL END AS sum_7d,
                CASE WHEN ps.count_14d >= ps.expected_14d * 0.98 THEN ps.sum_14d_raw ELSE NULL END AS sum_14d,
                CASE WHEN ps.count_30d >= ps.expected_30d * 0.98 THEN ps.sum_30d_raw ELSE NULL END AS sum_30d,
                CASE WHEN ps.count_90d >= ps.expected_90d * 0.98 THEN ps.sum_90d_raw ELSE NULL END AS sum_90d,
                CASE WHEN ps.count_180d >= ps.expected_180d * 0.98 THEN ps.sum_180d_raw ELSE NULL END AS sum_180d,
                CASE WHEN ps.count_365d >= ps.expected_365d * 0.98 THEN ps.sum_365d_raw ELSE NULL END AS sum_365d
            FROM period_sums ps;
            """
        ),
        {"contract_id": contract_id},
    )
    row = result.mappings().first()
    if not row:
        raise ValueError(f"Contract with id {contract_id} not found or has no data.")

    return FundingPeriodSums.model_validate(row)


async def get_funding_rate_differences(
    session: AsyncSession,
    asset_names: list[str] | None = None,
    section_names: list[str] | None = None,
    quote_names: list[str] | None = None,
    normalize_to_interval: NormalizeToInterval = NormalizeToInterval.D365,
    compare_for_section: str | None = None,
    min_diff: float | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> PaginatedFundingRateDifference:
    processed = FundingQueryComposer.process_filters(
        asset_names, section_names, quote_names, compare_for_section
    )
    query_sql = FundingQueryComposer.build_funding_rate_differences_query(
        normalize_to_interval, compare_for_section
    )

    result = await session.execute(
        text(query_sql),
        {
            **processed.to_dict(),
            "min_diff": min_diff if min_diff is not None else -1.0,
            "offset": offset,
            "limit": limit,
        },
    )
    rows = list(result.mappings())
    return _paginate_funding_rate(rows, offset, limit)


async def get_cumulative_funding_differences(
    session: AsyncSession,
    from_ts: int,
    to_ts: int,
    asset_names: list[str] | None = None,
    section_names: list[str] | None = None,
    quote_names: list[str] | None = None,
    compare_for_section: str | None = None,
    min_diff: float | None = None,
    buffer_minutes: int = 30,
    offset: int | None = None,
    limit: int | None = None,
) -> PaginatedCumulativeFundingDifference:
    processed = FundingQueryComposer.process_filters(
        asset_names, section_names, quote_names, compare_for_section
    )
    query_sql = FundingQueryComposer.build_cumulative_funding_differences_query(
        compare_for_section
    )

    result = await session.execute(
        text(query_sql),
        {
            **processed.to_dict(),
            "from_time": from_unix_seconds(from_ts),
            "to_time": from_unix_seconds(to_ts),
            "buffer_minutes": buffer_minutes,
            "min_diff": min_diff if min_diff is not None else -1.0,
            "offset": offset,
            "limit": limit,
        },
    )
    rows = list(result.mappings())
    return _paginate_cumulative(rows, offset, limit)


async def get_historical_funding_differences_avg(
    session: AsyncSession,
    from_ts: int,
    to_ts: int,
    normalize_to_interval: NormalizeToInterval,
    asset_names: list[str] | None = None,
    section_names: list[str] | None = None,
    quote_names: list[str] | None = None,
    compare_for_section: str | None = None,
    min_diff: float | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> PaginatedCumulativeFundingDifference:
    if normalize_to_interval == NormalizeToInterval.RAW:
        raise ValueError(
            "RAW normalization is not supported in get_historical_funding_differences_avg. "
            "Use get_cumulative_funding_differences for RAW data instead."
        )

    processed = FundingQueryComposer.process_filters(
        asset_names, section_names, quote_names, compare_for_section
    )
    query_sql = FundingQueryComposer.build_historical_funding_differences_avg_query(
        compare_for_section
    )

    result = await session.execute(
        text(query_sql),
        {
            **processed.to_dict(),
            "start_date": from_unix_seconds(from_ts),
            "end_date": from_unix_seconds(to_ts),
            "from_ts": from_ts,
            "to_ts": to_ts,
            "target_hours": FundingQueryComposer.calculate_target_hours(normalize_to_interval),
            "min_diff": min_diff if min_diff is not None else -1.0,
            "offset": offset,
            "limit": limit,
        },
    )
    rows = list(result.mappings())
    return _paginate_cumulative(rows, offset, limit)


async def get_funding_wall_live_raw(
    session: AsyncSession,
    asset_names: list[str],
    section_names: list[str],
) -> FundingWallResponse:
    result = await session.execute(
        text(FundingQueryComposer.build_funding_wall_live_raw_query()),
        {"asset_names": asset_names, "section_names": section_names},
    )
    rows = list(result.mappings())
    if not rows:
        return FundingWallResponse(
            timestamp=to_unix_seconds(utc_now()),
            assets=[],
            exchanges=section_names,
        )

    asset_data: dict[str, dict] = {}
    for row in rows:
        asset_name = row["asset_name"]
        if asset_name not in asset_data:
            asset_data[asset_name] = {
                "asset": asset_name,
                "market_cap_rank": row["market_cap_rank"],
                "rates": {},
            }
        asset_data[asset_name]["rates"][row["section_name"]] = row["funding_rate"]

    for asset_name in asset_data:
        for section_name in section_names:
            if section_name not in asset_data[asset_name]["rates"]:
                asset_data[asset_name]["rates"][section_name] = None

    assets = [FundingWallAsset.model_validate(data) for data in asset_data.values()]
    return FundingWallResponse(
        timestamp=rows[0]["timestamp"], assets=assets, exchanges=section_names
    )


async def get_funding_wall_live_normalized(
    session: AsyncSession,
    asset_names: list[str],
    section_names: list[str],
    normalize_to_interval: NormalizeToInterval,
) -> FundingWallResponse:
    result = await session.execute(
        text(FundingQueryComposer.build_funding_wall_live_normalized_query()),
        {
            "asset_names": asset_names,
            "section_names": section_names,
            "target_hours": FundingQueryComposer.calculate_target_hours(normalize_to_interval),
            "is_raw": normalize_to_interval == NormalizeToInterval.RAW,
        },
    )
    rows = list(result.mappings())
    if not rows:
        return FundingWallResponse(
            timestamp=to_unix_seconds(utc_now()),
            assets=[],
            exchanges=section_names,
        )

    asset_data: dict[str, dict] = {}
    for row in rows:
        asset_name = row["asset_name"]
        if asset_name not in asset_data:
            asset_data[asset_name] = {
                "asset": asset_name,
                "market_cap_rank": row["market_cap_rank"],
                "rates": {},
            }
        asset_data[asset_name]["rates"][row["section_name"]] = row["funding_rate"]

    for asset_name in asset_data:
        for section_name in section_names:
            if section_name not in asset_data[asset_name]["rates"]:
                asset_data[asset_name]["rates"][section_name] = None

    assets = [FundingWallAsset.model_validate(data) for data in asset_data.values()]
    return FundingWallResponse(
        timestamp=rows[0]["timestamp"], assets=assets, exchanges=section_names
    )


async def get_funding_wall_historical_raw(
    session: AsyncSession,
    asset_names: list[str],
    section_names: list[str],
    from_ts: int,
    to_ts: int,
) -> FundingWallResponse:
    result = await session.execute(
        text(FundingQueryComposer.build_funding_wall_historical_raw_query()),
        {
            "asset_names": asset_names,
            "section_names": section_names,
            "start_date": from_unix_seconds(from_ts),
            "end_date": from_unix_seconds(to_ts),
            "to_ts": to_ts,
        },
    )
    rows = list(result.mappings())
    if not rows:
        return FundingWallResponse(timestamp=to_ts, assets=[], exchanges=section_names)

    asset_data: dict[str, dict] = {}
    for row in rows:
        asset_name = row["asset_name"]
        if asset_name not in asset_data:
            asset_data[asset_name] = {
                "asset": asset_name,
                "market_cap_rank": row["market_cap_rank"],
                "rates": {},
            }
        asset_data[asset_name]["rates"][row["section_name"]] = row["funding_rate_sum"]

    for asset_name in asset_data:
        for section_name in section_names:
            if section_name not in asset_data[asset_name]["rates"]:
                asset_data[asset_name]["rates"][section_name] = None

    assets = [FundingWallAsset.model_validate(data) for data in asset_data.values()]
    return FundingWallResponse(timestamp=to_ts, assets=assets, exchanges=section_names)


_FILTERED_CONTRACTS_CTE = """
filtered_contracts AS (
    SELECT
        contracts.id AS contract_id,
        contracts.asset_name,
        contracts.quote_name,
        contracts.section_name,
        contracts.funding_interval
    FROM contract_enriched contracts
    WHERE ('all' = ANY(:asset_names) OR contracts.asset_name = ANY(:asset_names))
      AND ('all' = ANY(:section_names) OR contracts.section_name = ANY(:section_names))
      AND ('all' = ANY(:quote_names) OR contracts.quote_name = ANY(:quote_names))
)
"""


def _slice_params(
    asset_names: list[str] | None,
    section_names: list[str] | None,
    quote_names: list[str] | None,
) -> dict[str, list[str]]:
    return {
        "asset_names": asset_names if asset_names else ["all"],
        "section_names": section_names if section_names else ["all"],
        "quote_names": quote_names if quote_names else ["all"],
    }


def _normalization_params(normalize_to_interval: NormalizeToInterval) -> dict[str, float | bool]:
    is_raw = normalize_to_interval == NormalizeToInterval.RAW
    target_hours = (
        1.0 if is_raw else FundingQueryComposer.calculate_target_hours(normalize_to_interval)
    )
    return {"is_raw": is_raw, "target_hours": target_hours}


_LATEST_MULTIPLIER_SQL = (
    "CASE WHEN :is_raw THEN 1.0 "
    "WHEN fc.funding_interval > 0 THEN :target_hours / fc.funding_interval "
    "ELSE 1.0 END"
)


async def get_live_latest(
    session: AsyncSession,
    asset_names: list[str] | None,
    section_names: list[str] | None,
    quote_names: list[str] | None,
    normalize_to_interval: NormalizeToInterval,
) -> Sequence[LatestFundingPoint]:
    result = await session.execute(
        text(
            f"""
            WITH {_FILTERED_CONTRACTS_CTE}
            SELECT DISTINCT ON (fc.contract_id)
                fc.contract_id,
                fc.asset_name,
                fc.section_name,
                fc.quote_name,
                fc.funding_interval,
                (lfp.funding_rate * {_LATEST_MULTIPLIER_SQL}) AS funding_rate,
                EXTRACT(EPOCH FROM lfp.timestamp)::bigint AS timestamp
            FROM filtered_contracts fc
            LEFT JOIN live_funding_point lfp
                ON lfp.contract_id = fc.contract_id
                AND lfp.timestamp >= NOW() - INTERVAL '10 minutes'
            ORDER BY fc.contract_id, lfp.timestamp DESC NULLS LAST
            """
        ),
        {
            **_slice_params(asset_names, section_names, quote_names),
            **_normalization_params(normalize_to_interval),
        },
    )
    return [LatestFundingPoint.model_validate(row) for row in result.mappings().all()]


async def get_historical_latest(
    session: AsyncSession,
    asset_names: list[str] | None,
    section_names: list[str] | None,
    quote_names: list[str] | None,
    normalize_to_interval: NormalizeToInterval,
) -> Sequence[LatestFundingPoint]:
    # Contracts with no records in the last 30 days are considered invalid
    # and returned with funding_rate=null, timestamp=null.
    result = await session.execute(
        text(
            f"""
            WITH {_FILTERED_CONTRACTS_CTE}
            SELECT DISTINCT ON (fc.contract_id)
                fc.contract_id,
                fc.asset_name,
                fc.section_name,
                fc.quote_name,
                fc.funding_interval,
                (hfp.funding_rate * {_LATEST_MULTIPLIER_SQL}) AS funding_rate,
                EXTRACT(EPOCH FROM hfp.timestamp)::bigint AS timestamp
            FROM filtered_contracts fc
            LEFT JOIN historical_funding_point hfp
                ON hfp.contract_id = fc.contract_id
                AND hfp.timestamp >= NOW() - INTERVAL '30 days'
            ORDER BY fc.contract_id, hfp.timestamp DESC NULLS LAST
            """
        ),
        {
            **_slice_params(asset_names, section_names, quote_names),
            **_normalization_params(normalize_to_interval),
        },
    )
    return [LatestFundingPoint.model_validate(row) for row in result.mappings().all()]


async def get_historical_avg(
    session: AsyncSession,
    asset_names: list[str] | None,
    section_names: list[str] | None,
    quote_names: list[str] | None,
    windows_days: list[int],
    normalize_to_interval: NormalizeToInterval,
) -> Sequence[HistoricalAvgEntry]:
    max_days = max(windows_days)
    result = await session.execute(
        text(
            f"""
            WITH {_FILTERED_CONTRACTS_CTE},
            windows_cte AS (
                SELECT unnest(cast(:windows_days as integer[])) AS days
            ),
            funding_pool AS (
                SELECT
                    fc.contract_id,
                    fc.asset_name,
                    fc.section_name,
                    fc.quote_name,
                    fc.funding_interval,
                    hfp.funding_rate,
                    hfp.timestamp
                FROM filtered_contracts fc
                LEFT JOIN historical_funding_point hfp
                    ON hfp.contract_id = fc.contract_id
                    AND hfp.timestamp >= NOW() - make_interval(days => :max_days)
            ),
            per_window AS (
                SELECT
                    fp.contract_id,
                    fp.asset_name,
                    fp.section_name,
                    fp.quote_name,
                    fp.funding_interval,
                    w.days,
                    AVG(fp.funding_rate) FILTER (
                        WHERE fp.timestamp >= NOW() - make_interval(days => w.days)
                    ) AS avg_rate,
                    COUNT(fp.timestamp) FILTER (
                        WHERE fp.timestamp >= NOW() - make_interval(days => w.days)
                    ) AS points_count,
                    MIN(fp.timestamp) FILTER (
                        WHERE fp.timestamp >= NOW() - make_interval(days => w.days)
                    ) AS oldest_ts
                FROM funding_pool fp
                CROSS JOIN windows_cte w
                GROUP BY
                    fp.contract_id, fp.asset_name, fp.section_name, fp.quote_name,
                    fp.funding_interval, w.days
            )
            SELECT
                contract_id,
                asset_name,
                section_name,
                quote_name,
                funding_interval,
                days,
                (avg_rate * CASE
                    WHEN :is_raw THEN 1.0
                    WHEN funding_interval > 0 THEN :target_hours / funding_interval
                    ELSE 1.0
                END) AS funding_rate,
                points_count,
                CEIL(24.0 * days / NULLIF(funding_interval, 0))::int AS expected_count,
                EXTRACT(EPOCH FROM oldest_ts)::bigint AS oldest_timestamp
            FROM per_window
            ORDER BY asset_name, section_name, quote_name, days
            """
        ),
        {
            **_slice_params(asset_names, section_names, quote_names),
            **_normalization_params(normalize_to_interval),
            "windows_days": windows_days,
            "max_days": max_days,
        },
    )

    entries: dict[UUID, HistoricalAvgEntry] = {}
    for row in result.mappings().all():
        cid = row["contract_id"]
        entry = entries.get(cid)
        if entry is None:
            entry = HistoricalAvgEntry(
                contract_id=cid,
                asset_name=row["asset_name"],
                section_name=row["section_name"],
                quote_name=row["quote_name"],
                funding_interval=row["funding_interval"],
                windows=[],
            )
            entries[cid] = entry
        entry.windows.append(
            HistoricalAvgWindow(
                days=row["days"],
                funding_rate=row["funding_rate"],
                points_count=row["points_count"],
                expected_count=row["expected_count"],
                oldest_timestamp=row["oldest_timestamp"],
            )
        )
    return list(entries.values())


async def get_funding_wall_historical_normalized(
    session: AsyncSession,
    asset_names: list[str],
    section_names: list[str],
    from_ts: int,
    to_ts: int,
    normalize_to_interval: NormalizeToInterval,
) -> FundingWallResponse:
    result = await session.execute(
        text(FundingQueryComposer.build_funding_wall_historical_normalized_query()),
        {
            "asset_names": asset_names,
            "section_names": section_names,
            "start_date": from_unix_seconds(from_ts),
            "end_date": from_unix_seconds(to_ts),
            "target_hours": FundingQueryComposer.calculate_target_hours(normalize_to_interval),
            "to_ts": to_ts,
            "is_raw": normalize_to_interval == NormalizeToInterval.RAW,
        },
    )
    rows = list(result.mappings())
    if not rows:
        return FundingWallResponse(timestamp=to_ts, assets=[], exchanges=section_names)

    asset_data: dict[str, dict] = {}
    for row in rows:
        asset_name = row["asset_name"]
        if asset_name not in asset_data:
            asset_data[asset_name] = {
                "asset": asset_name,
                "market_cap_rank": row["market_cap_rank"],
                "rates": {},
            }
        asset_data[asset_name]["rates"][row["section_name"]] = row["funding_rate_avg_normalized"]

    for asset_name in asset_data:
        for section_name in section_names:
            if section_name not in asset_data[asset_name]["rates"]:
                asset_data[asset_name]["rates"][section_name] = None

    assets = [FundingWallAsset.model_validate(data) for data in asset_data.values()]
    return FundingWallResponse(timestamp=to_ts, assets=assets, exchanges=section_names)
