"use client";

import { fetchApiJson } from "../../_lib/api";
import { periodToApiRange, serializePeriod } from "./query-state";
import type {
  FilterOption,
  FundingArbitrageFilters,
  FundingArbitrageMeta,
  FundingArbitrageResponse,
  FundingArbitrageRow,
} from "./types";

type ApiBaseResponse<T> = {
  data: T;
  meta?: Record<string, unknown> | null;
};

type ApiNameList = {
  names: string[];
};

type ApiPaginatedResponse<T> = {
  data: T[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
};

type ApiLiveRow = {
  asset_name: string;
  contract_1_id: string;
  contract_1_section: string;
  contract_1_quote: string;
  contract_1_funding_rate: number;
  contract_2_id: string;
  contract_2_section: string;
  contract_2_quote: string;
  contract_2_funding_rate: number;
  difference: number;
  abs_difference: number;
};

type ApiHistoricalRow = {
  asset_name: string;
  contract_1_id: string;
  contract_1_section: string;
  contract_1_quote: string;
  contract_1_total_funding: number;
  contract_2_id: string;
  contract_2_section: string;
  contract_2_quote: string;
  contract_2_total_funding: number;
  difference: number;
  abs_difference: number;
  aligned_from: number;
  aligned_to: number;
};

function createOptions(values: string[]): FilterOption[] {
  return values.map((value) => ({
    value,
    label: value,
  }));
}

function mapLiveRow(row: ApiLiveRow): FundingArbitrageRow {
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

function mapHistoricalRow(row: ApiHistoricalRow): FundingArbitrageRow {
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
    fetchApiJson<ApiBaseResponse<ApiNameList>>("/api/v0/meta/assets", { signal }),
    fetchApiJson<ApiBaseResponse<ApiNameList>>("/api/v0/meta/sections", { signal }),
    fetchApiJson<ApiBaseResponse<ApiNameList>>("/api/v0/meta/quotes", { signal }),
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
    const response = await fetchApiJson<ApiPaginatedResponse<ApiLiveRow>>(path, {
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

  const response = await fetchApiJson<ApiPaginatedResponse<ApiHistoricalRow>>(path, {
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
