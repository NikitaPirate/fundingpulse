"use client";

import type {
  HistoricalAvgEntry,
  HistoricalAvgResponse,
  HistoricalLatestResponse,
  LiveLatestResponse,
  MetaAssetsResponse,
  MetaQuotesResponse,
  MetaSectionsResponse,
} from "../../_lib/api-contract";
import { fetchApiJson } from "../../_lib/api";
import type { FilterOption } from "../../_components/OptionsFilter";
import type {
  AssetFundingFilters,
  AssetFundingMeta,
  AssetFundingRow,
} from "./types";

function createOptions(values: string[]): FilterOption[] {
  return values.map((value) => ({
    value,
    label: value,
  }));
}

type MutableAssetFundingRow = Omit<AssetFundingRow, "live" | "lastSettled" | "avg7d" | "avg30d" | "avg90d" | "liveTimestamp" | "lastSettledTimestamp"> & {
  live: number | null;
  lastSettled: number | null;
  avg7d: number | null;
  avg30d: number | null;
  avg90d: number | null;
  liveTimestamp: number | null;
  lastSettledTimestamp: number | null;
};

function ensureRow(
  rows: Map<string, MutableAssetFundingRow>,
  entry: {
    contractId: string;
    assetName: string;
    section: string;
    quote: string;
    fundingInterval: number;
  },
) {
  const existing = rows.get(entry.contractId);
  if (existing) {
    return existing;
  }

  const next: MutableAssetFundingRow = {
    contractId: entry.contractId,
    assetName: entry.assetName,
    section: entry.section,
    quote: entry.quote,
    fundingInterval: entry.fundingInterval,
    live: null,
    lastSettled: null,
    avg7d: null,
    avg30d: null,
    avg90d: null,
    liveTimestamp: null,
    lastSettledTimestamp: null,
  };
  rows.set(entry.contractId, next);
  return next;
}

function applyHistoricalWindows(row: MutableAssetFundingRow, entry: HistoricalAvgEntry) {
  for (const window of entry.windows) {
    if (window.days === 7) {
      row.avg7d = window.funding_rate;
    }
    if (window.days === 30) {
      row.avg30d = window.funding_rate;
    }
    if (window.days === 90) {
      row.avg90d = window.funding_rate;
    }
  }
}

export async function fetchAssetFundingMeta(
  signal?: AbortSignal,
): Promise<AssetFundingMeta> {
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

export async function fetchAssetFundingRows(
  filters: AssetFundingFilters,
  signal?: AbortSignal,
): Promise<AssetFundingRow[]> {
  if (!filters.asset) {
    return [];
  }

  const params = new URLSearchParams();
  params.append("asset_names", filters.asset);

  for (const section of filters.sections) {
    params.append("section_names", section);
  }

  for (const quote of filters.quotes) {
    params.append("quote_names", quote);
  }

  params.set("normalize_to_interval", filters.normalize);

  const historicalAvgParams = new URLSearchParams(params.toString());
  historicalAvgParams.append("windows", "7");
  historicalAvgParams.append("windows", "30");
  historicalAvgParams.append("windows", "90");

  const [liveResponse, historicalLatestResponse, historicalAvgResponse] =
    await Promise.all([
      fetchApiJson<LiveLatestResponse>(`/api/v0/funding-data/live_latest?${params.toString()}`, {
        signal,
      }),
      fetchApiJson<HistoricalLatestResponse>(
        `/api/v0/funding-data/historical_latest?${params.toString()}`,
        { signal },
      ),
      fetchApiJson<HistoricalAvgResponse>(
        `/api/v0/funding-data/historical_avg?${historicalAvgParams.toString()}`,
        { signal },
      ),
    ]);

  const rows = new Map<string, MutableAssetFundingRow>();

  for (const row of liveResponse) {
    const merged = ensureRow(rows, {
      contractId: row.contract_id,
      assetName: row.asset_name,
      section: row.section_name,
      quote: row.quote_name,
      fundingInterval: row.funding_interval,
    });
    merged.live = row.funding_rate;
    merged.liveTimestamp = row.timestamp;
  }

  for (const row of historicalLatestResponse) {
    const merged = ensureRow(rows, {
      contractId: row.contract_id,
      assetName: row.asset_name,
      section: row.section_name,
      quote: row.quote_name,
      fundingInterval: row.funding_interval,
    });
    merged.lastSettled = row.funding_rate;
    merged.lastSettledTimestamp = row.timestamp;
  }

  for (const row of historicalAvgResponse) {
    const merged = ensureRow(rows, {
      contractId: row.contract_id,
      assetName: row.asset_name,
      section: row.section_name,
      quote: row.quote_name,
      fundingInterval: row.funding_interval,
    });
    applyHistoricalWindows(merged, row);
  }

  return [...rows.values()].filter(
    (row) =>
      row.live !== null ||
      row.lastSettled !== null ||
      row.avg7d !== null ||
      row.avg30d !== null ||
      row.avg90d !== null,
  );
}
