"use client";

import type {
  HistoricalDifferenceRow,
  HistoricalDifferencesResponse,
  LiveDifferenceRow,
  LiveDifferencesResponse,
  MetaAssetsResponse,
  MetaQuotesResponse,
  MetaSectionsResponse,
} from "../../_lib/api-contract";
import { fetchApiJson } from "../../_lib/api";
import { periodToApiRange, serializePeriod } from "./query-state";
import type {
  FilterOption,
  FundingArbitrageFilters,
  FundingArbitrageMeta,
  FundingArbitrageResponse,
  FundingArbitrageRow,
} from "./types";

function createOptions(values: string[]): FilterOption[] {
  return values.map((value) => ({
    value,
    label: value,
  }));
}

function mapLiveRow(row: LiveDifferenceRow): FundingArbitrageRow {
  return {
    kind: "live",
    assetName: row.asset_name,
    contract1: {
      id: row.contract_1_id,
      section: row.contract_1_section,
      quote: row.contract_1_quote,
      metric: row.contract_1_funding_rate,
    },
    contract2: {
      id: row.contract_2_id,
      section: row.contract_2_section,
      quote: row.contract_2_quote,
      metric: row.contract_2_funding_rate,
    },
    difference: row.difference,
    absDifference: row.abs_difference,
  };
}

function mapHistoricalRow(row: HistoricalDifferenceRow): FundingArbitrageRow {
  return {
    kind: "historical",
    assetName: row.asset_name,
    contract1: {
      id: row.contract_1_id,
      section: row.contract_1_section,
      quote: row.contract_1_quote,
      metric: row.contract_1_total_funding,
    },
    contract2: {
      id: row.contract_2_id,
      section: row.contract_2_section,
      quote: row.contract_2_quote,
      metric: row.contract_2_total_funding,
    },
    difference: row.difference,
    absDifference: row.abs_difference,
    alignedFrom: row.aligned_from,
    alignedTo: row.aligned_to,
  };
}

export async function fetchFundingArbitrageMeta(
  signal?: AbortSignal,
): Promise<FundingArbitrageMeta> {
  const [assetsResponse, sectionsResponse, quotesResponse] = await Promise.all([
    fetchApiJson<MetaAssetsResponse>("/api/v0/meta/assets", { signal }),
    fetchApiJson<MetaSectionsResponse>("/api/v0/meta/sections", { signal }),
    fetchApiJson<MetaQuotesResponse>("/api/v0/meta/quotes", { signal }),
  ]);

  return {
    assets: createOptions(assetsResponse.data.names),
    sections: createOptions(sectionsResponse.data.names),
    quotes: createOptions(quotesResponse.data.names),
  };
}

export async function fetchFundingArbitrageRows(
  filters: FundingArbitrageFilters,
  signal?: AbortSignal,
): Promise<FundingArbitrageResponse> {
  const params = new URLSearchParams();
  const isLive = serializePeriod(filters.period) === "live";

  for (const asset of filters.assets) {
    params.append("asset_names", asset);
  }

  for (const section of filters.sections) {
    params.append("section_names", section);
  }

  for (const quote of filters.quotes) {
    params.append("quote_names", quote);
  }

  params.set("normalize_to_interval", filters.normalize);
  params.set("offset", filters.offset.toString());
  params.set("limit", filters.limit.toString());

  if (filters.compareFor) {
    params.set("compare_for_section", filters.compareFor);
  }

  if (filters.minDiff !== null) {
    params.set("min_diff", filters.minDiff.toString());
  }

  if (!isLive) {
    const range = periodToApiRange(filters.period);
    if (range) {
      params.set("from_ts", range.fromTs.toString());
      params.set("to_ts", range.toTs.toString());
    }
  }

  const path = isLive
    ? `/api/v0/funding-data/diff/live_differences?${params.toString()}`
    : `/api/v0/funding-data/diff/historical_differences?${params.toString()}`;

  if (isLive) {
    const response = await fetchApiJson<LiveDifferencesResponse>(path, {
      signal,
    });

    return {
      data: response.data.map(mapLiveRow),
      totalCount: response.total_count,
      offset: response.offset,
      limit: response.limit,
      hasMore: response.has_more,
    };
  }

  const response = await fetchApiJson<HistoricalDifferencesResponse>(path, {
    signal,
  });

  return {
    data: response.data.map(mapHistoricalRow),
    totalCount: response.total_count,
    offset: response.offset,
    limit: response.limit,
    hasMore: response.has_more,
  };
}
