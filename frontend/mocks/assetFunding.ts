import type {
  HistoricalAvgEntry,
  HistoricalAvgResponse,
  HistoricalLatestRow,
  HistoricalLatestResponse,
  LiveLatestRow,
  LiveLatestResponse,
} from "../app/_lib/api-contract";
import { buildApiUrl } from "../app/_lib/api-runtime";
import { defaultFundingArbitrageFixtures } from "./fundingArbitrage";

export function apiUrl(path: string) {
  return buildApiUrl(path);
}

type MockContract = {
  contractId: string;
  assetName: string;
  sectionName: string;
  quoteName: string;
  fundingInterval: number;
  liveRaw: number | null;
  lastSettledRaw: number | null;
  avg7dRaw: number | null;
  avg30dRaw: number | null;
  avg90dRaw: number | null;
  liveTimestamp: number | null;
  lastSettledTimestamp: number | null;
};

const ASSET_NAMES = defaultFundingArbitrageFixtures.assets.data.names;
const SECTION_NAMES = defaultFundingArbitrageFixtures.sections.data.names;
const QUOTE_NAMES = defaultFundingArbitrageFixtures.quotes.data.names;
const NOW_TS = Date.UTC(2026, 3, 15, 12, 0, 0) / 1000;

function createContractId(assetName: string, sectionName: string, quoteName: string) {
  return `${assetName.toLowerCase()}-${sectionName}-${quoteName.toLowerCase()}`;
}

function applyNormalization(
  rawValue: number | null,
  fundingInterval: number,
  normalizeToInterval: string | null,
) {
  if (rawValue === null) {
    return null;
  }

  switch (normalizeToInterval) {
    case "1h":
      return rawValue * (1 / fundingInterval);
    case "8h":
      return rawValue * (8 / fundingInterval);
    case "1d":
      return rawValue * (24 / fundingInterval);
    case "365d":
      return rawValue * ((24 * 365) / fundingInterval);
    case "raw":
    default:
      return rawValue;
  }
}

function buildLiveLatestRow(overrides: Partial<LiveLatestRow> = {}): LiveLatestRow {
  return {
    contract_id: "btc-binance_usd-m-usdt",
    asset_name: "BTC",
    section_name: "binance_usd-m",
    quote_name: "USDT",
    funding_interval: 8,
    funding_rate: 0.0004,
    timestamp: NOW_TS,
    ...overrides,
  };
}

function buildHistoricalLatestRow(
  overrides: Partial<HistoricalLatestRow> = {},
): HistoricalLatestRow {
  return {
    contract_id: "btc-binance_usd-m-usdt",
    asset_name: "BTC",
    section_name: "binance_usd-m",
    quote_name: "USDT",
    funding_interval: 8,
    funding_rate: 0.00032,
    timestamp: NOW_TS - 8 * 60 * 60,
    ...overrides,
  };
}

function buildHistoricalAvgEntry(
  overrides: Partial<HistoricalAvgEntry> = {},
): HistoricalAvgEntry {
  return {
    contract_id: "btc-binance_usd-m-usdt",
    asset_name: "BTC",
    section_name: "binance_usd-m",
    quote_name: "USDT",
    funding_interval: 8,
    windows: [
      {
        days: 7,
        funding_rate: 0.00028,
        points_count: 21,
        expected_count: 21,
        oldest_timestamp: NOW_TS - 7 * 24 * 60 * 60,
      },
      {
        days: 30,
        funding_rate: 0.00021,
        points_count: 90,
        expected_count: 90,
        oldest_timestamp: NOW_TS - 30 * 24 * 60 * 60,
      },
      {
        days: 90,
        funding_rate: 0.00012,
        points_count: 270,
        expected_count: 270,
        oldest_timestamp: NOW_TS - 90 * 24 * 60 * 60,
      },
    ],
    ...overrides,
  };
}

function parseRequestedWindows(searchParams: URLSearchParams) {
  const windows = searchParams
    .getAll("windows")
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => Number.isFinite(value));

  return windows.length > 0 ? windows : [7, 30, 90];
}

function selectContracts(searchParams: URLSearchParams) {
  const assets = new Set(searchParams.getAll("asset_names").filter(Boolean));
  const sections = new Set(searchParams.getAll("section_names").filter(Boolean));
  const quotes = new Set(searchParams.getAll("quote_names").filter(Boolean));

  return mockContracts.filter((contract) => {
    if (assets.size > 0 && !assets.has(contract.assetName)) {
      return false;
    }

    if (sections.size > 0 && !sections.has(contract.sectionName)) {
      return false;
    }

    if (quotes.size > 0 && !quotes.has(contract.quoteName)) {
      return false;
    }

    return true;
  });
}

export function buildLiveLatestFixture(searchParams: URLSearchParams): LiveLatestResponse {
  return selectContracts(searchParams).map((contract) =>
    buildLiveLatestRow({
      contract_id: contract.contractId,
      asset_name: contract.assetName,
      section_name: contract.sectionName,
      quote_name: contract.quoteName,
      funding_interval: contract.fundingInterval,
      funding_rate: applyNormalization(
        contract.liveRaw,
        contract.fundingInterval,
        searchParams.get("normalize_to_interval"),
      ),
      timestamp: contract.liveTimestamp,
    }),
  );
}

export function buildHistoricalLatestFixture(
  searchParams: URLSearchParams,
): HistoricalLatestResponse {
  return selectContracts(searchParams).map((contract) =>
    buildHistoricalLatestRow({
      contract_id: contract.contractId,
      asset_name: contract.assetName,
      section_name: contract.sectionName,
      quote_name: contract.quoteName,
      funding_interval: contract.fundingInterval,
      funding_rate: applyNormalization(
        contract.lastSettledRaw,
        contract.fundingInterval,
        searchParams.get("normalize_to_interval"),
      ),
      timestamp: contract.lastSettledTimestamp,
    }),
  );
}

export function buildHistoricalAvgFixture(
  searchParams: URLSearchParams,
): HistoricalAvgResponse {
  const requestedWindows = parseRequestedWindows(searchParams);

  return selectContracts(searchParams).map((contract) =>
    buildHistoricalAvgEntry({
      contract_id: contract.contractId,
      asset_name: contract.assetName,
      section_name: contract.sectionName,
      quote_name: contract.quoteName,
      funding_interval: contract.fundingInterval,
      windows: requestedWindows.map((days) => ({
        days,
        funding_rate: applyNormalization(
          days === 7
            ? contract.avg7dRaw
            : days === 30
              ? contract.avg30dRaw
              : contract.avg90dRaw,
          contract.fundingInterval,
          searchParams.get("normalize_to_interval"),
        ),
        points_count: Math.floor((days * 24) / contract.fundingInterval),
        expected_count: Math.floor((days * 24) / contract.fundingInterval),
        oldest_timestamp: NOW_TS - days * 24 * 60 * 60,
      })),
    }),
  );
}

const mockContracts: MockContract[] = ASSET_NAMES.flatMap((assetName, assetIndex) =>
  SECTION_NAMES.flatMap((sectionName, sectionIndex) =>
    QUOTE_NAMES.map((quoteName, quoteIndex) => {
      const contractIndex =
        assetIndex * SECTION_NAMES.length * QUOTE_NAMES.length +
        sectionIndex * QUOTE_NAMES.length +
        quoteIndex;
      const fundingInterval = (assetIndex + sectionIndex + quoteIndex) % 3 === 0 ? 4 : 8;
      const basisPoints =
        (assetIndex - 4) * 0.35 + sectionIndex * 0.22 - quoteIndex * 0.18;
      const liveRaw = contractIndex % 11 === 0 ? null : basisPoints / 10_000;
      const lastSettledRaw =
        contractIndex % 7 === 0 ? null : (basisPoints * 0.82 + 0.07) / 10_000;
      const avg7dRaw = contractIndex % 5 === 0 ? null : (basisPoints * 0.74) / 10_000;
      const avg30dRaw = contractIndex % 6 === 0 ? null : (basisPoints * 0.58) / 10_000;
      const avg90dRaw = contractIndex % 4 === 0 ? null : (basisPoints * 0.41) / 10_000;

      return {
        contractId: createContractId(assetName, sectionName, quoteName),
        assetName,
        sectionName,
        quoteName,
        fundingInterval,
        liveRaw,
        lastSettledRaw,
        avg7dRaw,
        avg30dRaw,
        avg90dRaw,
        liveTimestamp: liveRaw === null ? null : NOW_TS - sectionIndex * 60,
        lastSettledTimestamp:
          lastSettledRaw === null ? null : NOW_TS - fundingInterval * 60 * 60,
      };
    }),
  ),
);
