import type {
  MetaAssetsResponse,
  MetaQuotesResponse,
  MetaSectionsResponse,
  HistoricalDifferenceRow,
  HistoricalDifferencesResponse,
  LiveDifferenceRow,
  LiveDifferencesResponse,
} from "../app/_lib/api-contract";
import { buildApiUrl } from "../app/_lib/api-runtime";

export function apiUrl(path: string) {
  return buildApiUrl(path);
}

export function buildAssetsResponse(names: string[]): MetaAssetsResponse {
  return {
    data: { names },
    meta: null,
  };
}

export function buildSectionsResponse(names: string[]): MetaSectionsResponse {
  return {
    data: { names },
    meta: null,
  };
}

export function buildQuotesResponse(names: string[]): MetaQuotesResponse {
  return {
    data: { names },
    meta: null,
  };
}

export function buildLiveDifferenceRow(
  overrides: Partial<LiveDifferenceRow> = {},
): LiveDifferenceRow {
  return {
    asset_name: "BTC",
    contract_1_id: "6b390f17-aed3-41bc-991f-f49f04b8c4cf",
    contract_1_section: "binance_usd-m",
    contract_1_quote: "USDT",
    contract_1_funding_rate: 0.0004,
    contract_2_id: "8f6d0511-1bd6-48c7-8586-f839ad130ef2",
    contract_2_section: "bybit",
    contract_2_quote: "USDT",
    contract_2_funding_rate: -0.0001,
    difference: 0.0005,
    abs_difference: 0.0005,
    ...overrides,
  };
}

export function buildHistoricalDifferenceRow(
  overrides: Partial<HistoricalDifferenceRow> = {},
): HistoricalDifferenceRow {
  return {
    asset_name: "BTC",
    contract_1_id: "6b390f17-aed3-41bc-991f-f49f04b8c4cf",
    contract_1_section: "binance_usd-m",
    contract_1_quote: "USDT",
    contract_1_total_funding: 0.0024,
    contract_2_id: "8f6d0511-1bd6-48c7-8586-f839ad130ef2",
    contract_2_section: "bybit",
    contract_2_quote: "USDT",
    contract_2_total_funding: -0.0006,
    difference: 0.003,
    abs_difference: 0.003,
    aligned_from: 1_710_000_000,
    aligned_to: 1_710_086_400,
    ...overrides,
  };
}

export function buildLiveDifferencesResponse(
  rows: LiveDifferenceRow[],
  overrides: Partial<Omit<LiveDifferencesResponse, "data">> = {},
): LiveDifferencesResponse {
  return {
    data: rows,
    total_count: rows.length,
    offset: 0,
    limit: 20,
    has_more: false,
    ...overrides,
  };
}

export function buildHistoricalDifferencesResponse(
  rows: HistoricalDifferenceRow[],
  overrides: Partial<Omit<HistoricalDifferencesResponse, "data">> = {},
): HistoricalDifferencesResponse {
  return {
    data: rows,
    total_count: rows.length,
    offset: 0,
    limit: 20,
    has_more: false,
    ...overrides,
  };
}

export const defaultFundingArbitrageFixtures = {
  assets: buildAssetsResponse(["BTC", "ETH", "SOL"]),
  sections: buildSectionsResponse(["binance_usd-m", "bybit", "okx"]),
  quotes: buildQuotesResponse(["USDT", "USDC"]),
  live: buildLiveDifferencesResponse([
    buildLiveDifferenceRow(),
    buildLiveDifferenceRow({
      asset_name: "ETH",
      contract_1_id: "c2ddcdd9-f3f8-4068-a380-48d66931d010",
      contract_1_section: "okx",
      contract_2_id: "2032d73d-6497-4a6d-9d2b-db67988df841",
      contract_2_section: "bybit",
      contract_1_funding_rate: -0.0002,
      contract_2_funding_rate: 0.0004,
      difference: -0.0006,
      abs_difference: 0.0006,
    }),
  ]),
  historical: buildHistoricalDifferencesResponse([
    buildHistoricalDifferenceRow(),
  ]),
};
