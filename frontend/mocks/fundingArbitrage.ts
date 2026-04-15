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

const HOUR_IN_SECONDS = 60 * 60;
const DAY_IN_SECONDS = 24 * HOUR_IN_SECONDS;
const DEFAULT_LIMIT = 20;
const DEFAULT_HISTORICAL_WINDOW = 30 * DAY_IN_SECONDS;
const DEFAULT_HISTORICAL_TO = Date.UTC(2026, 3, 15, 12, 0, 0) / 1000;
const DEFAULT_HISTORICAL_FROM = DEFAULT_HISTORICAL_TO - DEFAULT_HISTORICAL_WINDOW;

const ASSET_NAMES = [
  "BTC",
  "ETH",
  "SOL",
  "XRP",
  "DOGE",
  "ADA",
  "AVAX",
  "LINK",
  "TON",
  "BNB",
  "SUI",
  "APT",
];

const SECTION_NAMES = [
  "binance_usd-m",
  "bybit",
  "okx",
  "bitget",
  "hyperliquid",
];

const QUOTE_NAMES = ["USDT", "USDC"];

const SECTION_PAIRS: Array<[string, string]> = [
  ["binance_usd-m", "bybit"],
  ["binance_usd-m", "okx"],
  ["binance_usd-m", "bitget"],
  ["binance_usd-m", "hyperliquid"],
  ["bybit", "okx"],
  ["bybit", "bitget"],
  ["bybit", "hyperliquid"],
  ["okx", "bitget"],
  ["okx", "hyperliquid"],
  ["bitget", "hyperliquid"],
];

type MockPair = {
  assetName: string;
  contract1Section: string;
  contract2Section: string;
  quote: string;
  baseRate1: number;
  baseRate2: number;
  availableFrom: number;
  availableTo: number;
};

function createContractId(assetName: string, section: string, quote: string) {
  return `${assetName.toLowerCase()}-${section}-${quote.toLowerCase()}`;
}

function normalizationFactor(rawValue: string | null) {
  switch (rawValue) {
    case "1h":
      return 1 / 8;
    case "8h":
      return 1;
    case "1d":
      return 3;
    case "365d":
      return 365 / 8;
    case "raw":
    default:
      return 1;
  }
}

function parseBoundedInteger(
  rawValue: string | null,
  fallback: number,
  min: number,
  max: number,
) {
  if (!rawValue) {
    return fallback;
  }

  const parsed = Number.parseInt(rawValue, 10);
  if (Number.isNaN(parsed)) {
    return fallback;
  }

  return Math.min(Math.max(parsed, min), max);
}

function parseFiniteNumber(rawValue: string | null) {
  if (!rawValue) {
    return null;
  }

  const parsed = Number.parseFloat(rawValue);
  return Number.isFinite(parsed) ? parsed : null;
}

function selectPairs(searchParams: URLSearchParams) {
  const assets = new Set(searchParams.getAll("asset_names").filter(Boolean));
  const sections = new Set(searchParams.getAll("section_names").filter(Boolean));
  const quotes = new Set(searchParams.getAll("quote_names").filter(Boolean));
  const compareForSection = searchParams.get("compare_for_section");

  return mockPairs.filter((pair) => {
    if (assets.size > 0 && !assets.has(pair.assetName)) {
      return false;
    }

    if (
      sections.size > 0 &&
      (!sections.has(pair.contract1Section) || !sections.has(pair.contract2Section))
    ) {
      return false;
    }

    if (quotes.size > 0 && !quotes.has(pair.quote)) {
      return false;
    }

    if (
      compareForSection &&
      compareForSection !== pair.contract1Section &&
      compareForSection !== pair.contract2Section
    ) {
      return false;
    }

    return true;
  });
}

function historicalWindow(searchParams: URLSearchParams) {
  const fromTs = parseBoundedInteger(
    searchParams.get("from_ts"),
    DEFAULT_HISTORICAL_FROM,
    0,
    Number.MAX_SAFE_INTEGER,
  );
  const toTs = parseBoundedInteger(
    searchParams.get("to_ts"),
    DEFAULT_HISTORICAL_TO,
    fromTs + HOUR_IN_SECONDS,
    Number.MAX_SAFE_INTEGER,
  );

  return { fromTs, toTs };
}

function applyMinDiff<T extends { abs_difference: number }>(
  rows: T[],
  minDiff: number | null,
) {
  if (minDiff === null) {
    return rows;
  }

  return rows.filter((row) => row.abs_difference >= minDiff);
}

function paginate<T>(rows: T[], searchParams: URLSearchParams) {
  const offset = parseBoundedInteger(searchParams.get("offset"), 0, 0, rows.length);
  const limit = parseBoundedInteger(searchParams.get("limit"), DEFAULT_LIMIT, 1, 100);

  return {
    rows: rows.slice(offset, offset + limit),
    totalCount: rows.length,
    offset,
    limit,
    hasMore: offset + limit < rows.length,
  };
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

function createLiveRow(pair: MockPair, normalizeToInterval: string | null): LiveDifferenceRow {
  const factor = normalizationFactor(normalizeToInterval);
  const contract1FundingRate = pair.baseRate1 * factor;
  const contract2FundingRate = pair.baseRate2 * factor;
  const difference = contract1FundingRate - contract2FundingRate;

  return buildLiveDifferenceRow({
    asset_name: pair.assetName,
    contract_1_id: createContractId(pair.assetName, pair.contract1Section, pair.quote),
    contract_1_section: pair.contract1Section,
    contract_1_quote: pair.quote,
    contract_1_funding_rate: contract1FundingRate,
    contract_2_id: createContractId(pair.assetName, pair.contract2Section, pair.quote),
    contract_2_section: pair.contract2Section,
    contract_2_quote: pair.quote,
    contract_2_funding_rate: contract2FundingRate,
    difference,
    abs_difference: Math.abs(difference),
  });
}

function createHistoricalRow(
  pair: MockPair,
  normalizeToInterval: string | null,
  fromTs: number,
  toTs: number,
) {
  const alignedFrom = Math.max(pair.availableFrom, fromTs);
  const alignedTo = Math.min(pair.availableTo, toTs);

  if (alignedFrom >= alignedTo) {
    return null;
  }

  const windowFactor =
    normalizeToInterval === "raw"
      ? (alignedTo - alignedFrom) / (8 * HOUR_IN_SECONDS)
      : normalizationFactor(normalizeToInterval);

  const contract1TotalFunding = pair.baseRate1 * windowFactor;
  const contract2TotalFunding = pair.baseRate2 * windowFactor;
  const difference = contract1TotalFunding - contract2TotalFunding;

  return buildHistoricalDifferenceRow({
    asset_name: pair.assetName,
    contract_1_id: createContractId(pair.assetName, pair.contract1Section, pair.quote),
    contract_1_section: pair.contract1Section,
    contract_1_quote: pair.quote,
    contract_1_total_funding: contract1TotalFunding,
    contract_2_id: createContractId(pair.assetName, pair.contract2Section, pair.quote),
    contract_2_section: pair.contract2Section,
    contract_2_quote: pair.quote,
    contract_2_total_funding: contract2TotalFunding,
    difference,
    abs_difference: Math.abs(difference),
    aligned_from: alignedFrom,
    aligned_to: alignedTo,
  });
}

export function buildLiveDifferencesFixture(
  searchParams: URLSearchParams,
): LiveDifferencesResponse {
  const rows = applyMinDiff(
    selectPairs(searchParams)
      .map((pair) => createLiveRow(pair, searchParams.get("normalize_to_interval")))
      .sort((left, right) => right.abs_difference - left.abs_difference),
    parseFiniteNumber(searchParams.get("min_diff")),
  );
  const page = paginate(rows, searchParams);

  return buildLiveDifferencesResponse(page.rows, {
    total_count: page.totalCount,
    offset: page.offset,
    limit: page.limit,
    has_more: page.hasMore,
  });
}

export function buildHistoricalDifferencesFixture(
  searchParams: URLSearchParams,
): HistoricalDifferencesResponse {
  const { fromTs, toTs } = historicalWindow(searchParams);
  const rows = applyMinDiff(
    selectPairs(searchParams)
      .map((pair) => createHistoricalRow(pair, searchParams.get("normalize_to_interval"), fromTs, toTs))
      .filter((row): row is HistoricalDifferenceRow => row !== null)
      .sort((left, right) => right.abs_difference - left.abs_difference),
    parseFiniteNumber(searchParams.get("min_diff")),
  );
  const page = paginate(rows, searchParams);

  return buildHistoricalDifferencesResponse(page.rows, {
    total_count: page.totalCount,
    offset: page.offset,
    limit: page.limit,
    has_more: page.hasMore,
  });
}

export function buildDefaultSearchParams() {
  return new URLSearchParams([
    ["normalize_to_interval", "365d"],
    ["limit", String(DEFAULT_LIMIT)],
  ]);
}

const mockPairs: MockPair[] = ASSET_NAMES.flatMap((assetName, assetIndex) =>
  SECTION_PAIRS.map(([contract1Section, contract2Section], pairIndex) => {
    const quote = QUOTE_NAMES[(assetIndex + pairIndex) % QUOTE_NAMES.length];
    const spreadBasisPoints = 6 + assetIndex * 1.5 + pairIndex * 2.35;
    const midpointBasisPoints = ((assetIndex * 5 + pairIndex * 3) % 11) - 5;
    const spread = spreadBasisPoints / 10_000;
    const midpoint = midpointBasisPoints / 100_000;
    const direction = (assetIndex + pairIndex) % 2 === 0 ? 1 : -1;
    const availableFrom =
      DEFAULT_HISTORICAL_FROM - (assetIndex * 2 + pairIndex) * DAY_IN_SECONDS;
    const availableTo =
      DEFAULT_HISTORICAL_TO - ((assetIndex + pairIndex) % 6) * HOUR_IN_SECONDS;

    return {
      assetName,
      contract1Section,
      contract2Section,
      quote,
      baseRate1: midpoint + (direction * spread) / 2,
      baseRate2: midpoint - (direction * spread) / 2,
      availableFrom,
      availableTo,
    };
  }),
);

export const defaultFundingArbitrageFixtures = {
  assets: buildAssetsResponse(ASSET_NAMES),
  sections: buildSectionsResponse(SECTION_NAMES),
  quotes: buildQuotesResponse(QUOTE_NAMES),
  live: buildLiveDifferencesFixture(buildDefaultSearchParams()),
  historical: buildHistoricalDifferencesFixture(buildDefaultSearchParams()),
};
