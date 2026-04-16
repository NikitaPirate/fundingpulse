import type {
  ContractMetaResponse,
  ContractSearchResponse,
  FundingPointResponse,
  HistoricalSumsResponse,
} from "../app/_lib/api-contract";
import {
  NOW_TS,
  applyNormalization,
  getMockContract,
  historicalAvgRawForWindow,
  mockContracts,
  parseRequestedWindows,
  selectContracts,
} from "./assetFunding";

function normalizeText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function prefixScore(query: string, candidate: string) {
  const normalizedQuery = normalizeText(query);
  const normalizedCandidate = normalizeText(candidate);

  if (normalizedCandidate.startsWith(normalizedQuery)) {
    return 100 - (normalizedCandidate.length - normalizedQuery.length);
  }

  if (normalizedCandidate.includes(normalizedQuery)) {
    return 60 - normalizedCandidate.indexOf(normalizedQuery);
  }

  return -1;
}

function contractSearchScore(query: string, contract: (typeof mockContracts)[number]) {
  const label = `${contract.assetName} ${contract.sectionName} ${contract.quoteName}`;

  return Math.max(
    prefixScore(query, contract.assetName),
    prefixScore(query, contract.sectionName),
    prefixScore(query, contract.quoteName),
    prefixScore(query, label),
  );
}

function baseRaw(contractId: string) {
  const contract = getMockContract(contractId);
  if (!contract) {
    return 0.00002;
  }

  return (
    contract.liveRaw ??
    contract.lastSettledRaw ??
    contract.avg7dRaw ??
    contract.avg30dRaw ??
    contract.avg90dRaw ??
    0.00002
  );
}

function hashContractId(contractId: string) {
  let hash = 0;

  for (let index = 0; index < contractId.length; index += 1) {
    hash = (hash * 33 + contractId.charCodeAt(index)) >>> 0;
  }

  return hash;
}

export function buildContractMetaFixture(contractId: string): ContractMetaResponse | null {
  const contract = getMockContract(contractId);
  if (!contract) {
    return null;
  }

  return {
    data: {
      id: contract.contractId,
      asset_name: contract.assetName,
      section_name: contract.sectionName,
      quote_name: contract.quoteName,
      funding_interval: contract.fundingInterval,
      special_fields: {},
      synced: true,
      deprecated: false,
    },
    meta: null,
  };
}

export function buildContractSearchFixture(
  query: string,
  limit = 10,
): ContractSearchResponse {
  const normalizedQuery = query.trim();
  const contracts =
    normalizedQuery.length === 0
      ? []
      : mockContracts
          .map((contract) => ({
            contract,
            score: contractSearchScore(normalizedQuery, contract),
          }))
          .filter((entry) => entry.score >= 0)
          .toSorted((left, right) => right.score - left.score)
          .slice(0, limit)
          .map(({ contract, score }) => ({
            id: contract.contractId,
            asset_name: contract.assetName,
            section_name: contract.sectionName,
            quote_name: contract.quoteName,
            funding_interval: contract.fundingInterval,
            relevance_score: score,
            asset_score: null,
            section_score: null,
            quote_score: null,
            fuzzy_score: null,
          }));

  return {
    data: {
      contracts,
    },
    meta: null,
  };
}

export function buildHistoricalSumsFixture(
  searchParams: URLSearchParams,
): HistoricalSumsResponse {
  const requestedWindows = parseRequestedWindows(searchParams);

  return selectContracts(searchParams).map((contract) => ({
    contract_id: contract.contractId,
    asset_name: contract.assetName,
    section_name: contract.sectionName,
    quote_name: contract.quoteName,
    funding_interval: contract.fundingInterval,
    windows: requestedWindows.map((days) => {
      const avgRaw = historicalAvgRawForWindow(contract, days);
      const pointsCount = Math.floor((days * 24) / contract.fundingInterval);
      const rawSum = avgRaw === null ? null : avgRaw * pointsCount;

      return {
        days,
        funding_rate: applyNormalization(
          rawSum,
          contract.fundingInterval,
          searchParams.get("normalize_to_interval"),
        ),
        points_count: pointsCount,
        expected_count: pointsCount,
        oldest_timestamp: NOW_TS - days * 24 * 60 * 60,
      };
    }),
  }));
}

export function buildLivePointsFixture(
  searchParams: URLSearchParams,
): FundingPointResponse {
  const contractId = searchParams.get("contract_id");
  const fromTs = Number.parseInt(searchParams.get("from_ts") ?? "", 10);
  const toTs = Number.parseInt(searchParams.get("to_ts") ?? "", 10);

  if (!contractId || !Number.isFinite(fromTs) || !Number.isFinite(toTs) || fromTs >= toTs) {
    return [];
  }

  const contract = getMockContract(contractId);
  if (!contract) {
    return [];
  }

  const base = baseRaw(contractId);
  const seed = hashContractId(contractId) % 17;
  const points: FundingPointResponse = [];
  const step = 5 * 60;

  for (let timestamp = fromTs; timestamp <= toTs; timestamp += step) {
    const pointIndex = Math.floor((timestamp - fromTs) / step);
    const rawValue =
      base +
      Math.sin(pointIndex / 9 + seed) * 0.00002 +
      Math.cos(pointIndex / 17 + seed) * 0.00001;

    points.push({
      contract_id: contractId,
      timestamp,
      funding_rate:
        applyNormalization(
          rawValue,
          contract.fundingInterval,
          searchParams.get("normalize_to_interval"),
        ) ?? 0,
    });
  }

  return points;
}

export function buildHistoricalPointsFixture(
  searchParams: URLSearchParams,
): FundingPointResponse {
  const contractId = searchParams.get("contract_id");
  const fromTs = Number.parseInt(searchParams.get("from_ts") ?? "", 10);
  const toTs = Number.parseInt(searchParams.get("to_ts") ?? "", 10);

  if (!contractId || !Number.isFinite(fromTs) || !Number.isFinite(toTs) || fromTs >= toTs) {
    return [];
  }

  const contract = getMockContract(contractId);
  if (!contract) {
    return [];
  }

  const base = baseRaw(contractId) * 0.86;
  const seed = hashContractId(contractId) % 23;
  const points: FundingPointResponse = [];
  const step = contract.fundingInterval * 60 * 60;

  for (let timestamp = fromTs; timestamp <= toTs; timestamp += step) {
    const pointIndex = Math.floor((timestamp - fromTs) / step);
    const rawValue = base + Math.sin(pointIndex / 5 + seed) * 0.00003;

    points.push({
      contract_id: contractId,
      timestamp,
      funding_rate:
        applyNormalization(
          rawValue,
          contract.fundingInterval,
          searchParams.get("normalize_to_interval"),
        ) ?? 0,
    });
  }

  return points;
}
