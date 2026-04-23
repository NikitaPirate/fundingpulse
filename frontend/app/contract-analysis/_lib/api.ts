"use client";

import type {
  ContractMetaResponse,
  ContractSearchResponse,
  FundingPointResponse,
  HistoricalAvgResponse,
  HistoricalLatestResponse,
  HistoricalSumsResponse,
  LiveLatestResponse,
} from "../../_lib/api-contract";
import { fetchApiJson } from "../../_lib/api";
import {
  SUMMARY_WINDOWS,
  type ContractMeta,
  type ContractSearchResult,
  type FundingPoint,
  type Normalization,
  type PairSummary,
  type SingleContractSummary,
  type SummaryWindowMap,
  type WindowDays,
} from "./types";

function createEmptyWindowMap(): SummaryWindowMap {
  return {
    7: null,
    14: null,
    30: null,
    90: null,
    180: null,
    365: null,
  };
}

function createEmptySummary(): SingleContractSummary {
  return {
    liveRate: null,
    liveTimestamp: null,
    lastSettledRate: null,
    lastSettledTimestamp: null,
    avgWindows: createEmptyWindowMap(),
    accumulatedWindows: createEmptyWindowMap(),
  };
}

function mapContractMeta(response: ContractMetaResponse): ContractMeta {
  return {
    id: response.data.id,
    assetName: response.data.asset_name,
    sectionName: response.data.section_name,
    quoteName: response.data.quote_name,
    fundingInterval: response.data.funding_interval,
    deprecated: response.data.deprecated,
  };
}

function mapSearchResult(
  result: ContractSearchResponse["data"]["contracts"][number],
): ContractSearchResult {
  return {
    id: result.id,
    assetName: result.asset_name,
    sectionName: result.section_name,
    quoteName: result.quote_name,
    fundingInterval: result.funding_interval,
    relevanceScore: result.relevance_score,
  };
}

function applyWindowEntries(
  target: SummaryWindowMap,
  windows: Array<{
    days: number;
    funding_rate: number | null;
  }>,
) {
  for (const window of windows) {
    if (SUMMARY_WINDOWS.includes(window.days as WindowDays)) {
      target[window.days as WindowDays] = window.funding_rate;
    }
  }
}

function subtractNullable(left: number | null, right: number | null) {
  if (left === null || right === null) {
    return null;
  }

  return left - right;
}

function sliceParams(meta: ContractMeta, normalize: Normalization) {
  const params = new URLSearchParams();
  params.append("asset_names", meta.assetName);
  params.append("section_names", meta.sectionName);
  params.append("quote_names", meta.quoteName);
  params.set("normalize_to_interval", normalize);
  return params;
}

function summaryKey(meta: ContractMeta, normalize: Normalization) {
  return `${meta.id}:${normalize}`;
}

export function getSummaryKey(meta: ContractMeta, normalize: Normalization) {
  return summaryKey(meta, normalize);
}

export async function fetchContractMeta(
  contractId: string,
  signal?: AbortSignal,
): Promise<ContractMeta> {
  const response = await fetchApiJson<ContractMetaResponse>(
    `/api/v0/meta/contracts/${contractId}`,
    { signal },
  );

  return mapContractMeta(response);
}

export async function fetchContractSearch(
  query: string,
  limit = 10,
  signal?: AbortSignal,
): Promise<ContractSearchResult[]> {
  const params = new URLSearchParams();
  params.set("query", query);
  params.set("limit", limit.toString());

  const response = await fetchApiJson<ContractSearchResponse>(
    `/api/v0/meta/contracts/search?${params.toString()}`,
    { signal },
  );

  return response.data.contracts.map(mapSearchResult);
}

export async function fetchContractSummary(
  meta: ContractMeta,
  normalize: Normalization,
  signal?: AbortSignal,
): Promise<SingleContractSummary> {
  const params = sliceParams(meta, normalize);
  const windowsParams = new URLSearchParams(params.toString());
  for (const window of SUMMARY_WINDOWS) {
    windowsParams.append("windows", window.toString());
  }

  const [liveResponse, historicalLatestResponse, historicalAvgResponse, historicalSumsResponse] =
    await Promise.all([
      fetchApiJson<LiveLatestResponse>(`/api/v0/funding-data/live_latest?${params.toString()}`, {
        signal,
      }),
      fetchApiJson<HistoricalLatestResponse>(
        `/api/v0/funding-data/historical_latest?${params.toString()}`,
        { signal },
      ),
      fetchApiJson<HistoricalAvgResponse>(
        `/api/v0/funding-data/historical_avg?${windowsParams.toString()}`,
        { signal },
      ),
      fetchApiJson<HistoricalSumsResponse>(
        `/api/v0/funding-data/historical_sums?${windowsParams.toString()}`,
        { signal },
      ),
    ]);

  const summary = createEmptySummary();

  const liveRow = liveResponse.find((row) => row.contract_id === meta.id);
  if (liveRow) {
    summary.liveRate = liveRow.funding_rate;
    summary.liveTimestamp = liveRow.timestamp;
  }

  const settledRow = historicalLatestResponse.find((row) => row.contract_id === meta.id);
  if (settledRow) {
    summary.lastSettledRate = settledRow.funding_rate;
    summary.lastSettledTimestamp = settledRow.timestamp;
  }

  const avgRow = historicalAvgResponse.find((row) => row.contract_id === meta.id);
  if (avgRow) {
    applyWindowEntries(summary.avgWindows, avgRow.windows);
  }

  const sumsRow = historicalSumsResponse.find((row) => row.contract_id === meta.id);
  if (sumsRow) {
    applyWindowEntries(summary.accumulatedWindows, sumsRow.windows);
  }

  return summary;
}

export function computePairSummary(
  c1: SingleContractSummary,
  c2: SingleContractSummary,
): PairSummary {
  const avgSpreadWindows = createEmptyWindowMap();
  const accumulatedSpreadWindows = createEmptyWindowMap();

  for (const window of SUMMARY_WINDOWS) {
    avgSpreadWindows[window] = subtractNullable(c1.avgWindows[window], c2.avgWindows[window]);
    accumulatedSpreadWindows[window] = subtractNullable(
      c1.accumulatedWindows[window],
      c2.accumulatedWindows[window],
    );
  }

  return {
    c1,
    c2,
    currentSpread: subtractNullable(c1.liveRate, c2.liveRate),
    lastSettledSpread: subtractNullable(c1.lastSettledRate, c2.lastSettledRate),
    lastSettledTimestamp: Math.max(c1.lastSettledTimestamp ?? 0, c2.lastSettledTimestamp ?? 0) || null,
    avgSpreadWindows,
    accumulatedSpreadWindows,
  };
}

export async function fetchLivePoints(
  contractId: string,
  fromTs: number,
  toTs: number,
  normalize: Normalization,
  signal?: AbortSignal,
): Promise<FundingPoint[]> {
  const params = new URLSearchParams();
  params.set("contract_id", contractId);
  params.set("from_ts", fromTs.toString());
  params.set("to_ts", toTs.toString());
  params.set("normalize_to_interval", normalize);

  const response = await fetchApiJson<FundingPointResponse>(
    `/api/v0/funding-data/live_points?${params.toString()}`,
    { signal },
  );

  return response.map((point) => ({
    contractId: point.contract_id,
    timestamp: point.timestamp,
    fundingRate: point.funding_rate,
  }));
}

export async function fetchHistoricalPoints(
  contractId: string,
  fromTs: number,
  toTs: number,
  normalize: Normalization,
  signal?: AbortSignal,
): Promise<FundingPoint[]> {
  const params = new URLSearchParams();
  params.set("contract_id", contractId);
  params.set("from_ts", fromTs.toString());
  params.set("to_ts", toTs.toString());
  params.set("normalize_to_interval", normalize);

  const response = await fetchApiJson<FundingPointResponse>(
    `/api/v0/funding-data/historical_points?${params.toString()}`,
    { signal },
  );

  return response.map((point) => ({
    contractId: point.contract_id,
    timestamp: point.timestamp,
    fundingRate: point.funding_rate,
  }));
}
