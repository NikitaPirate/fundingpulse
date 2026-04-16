export type Normalization = "raw" | "1h" | "8h" | "1d" | "365d";

export type AnalysisMode = "empty" | "single" | "pair";

export type ContractAnalysisParams = {
  c1: string | null;
  c2: string | null;
  normalize: Normalization;
};

export type ContractMeta = {
  id: string;
  assetName: string;
  sectionName: string;
  quoteName: string;
  fundingInterval: number;
  synced: boolean;
  deprecated: boolean;
};

export type ContractSearchResult = {
  id: string;
  assetName: string;
  sectionName: string;
  quoteName: string;
  fundingInterval: number;
  relevanceScore: number;
};

export const SUMMARY_WINDOWS = [7, 14, 30, 90, 180, 365] as const;
export type WindowDays = (typeof SUMMARY_WINDOWS)[number];
export type SummaryWindowMap = Record<WindowDays, number | null>;

export type SingleContractSummary = {
  liveRate: number | null;
  liveTimestamp: number | null;
  lastSettledRate: number | null;
  lastSettledTimestamp: number | null;
  avgWindows: SummaryWindowMap;
  accumulatedWindows: SummaryWindowMap;
};

export type PairSummary = {
  c1: SingleContractSummary;
  c2: SingleContractSummary;
  currentSpread: number | null;
  lastSettledSpread: number | null;
  lastSettledTimestamp: number | null;
  avgSpreadWindows: SummaryWindowMap;
  accumulatedSpreadWindows: SummaryWindowMap;
};

export type MetaState = {
  contractId: string | null;
  meta: ContractMeta | null;
  error: string | null;
  settledId: string | null;
};

export type SummaryState = {
  contractId: string | null;
  summary: SingleContractSummary | null;
  error: string | null;
  settledKey: string | null;
};

export type FundingPoint = {
  contractId: string;
  timestamp: number;
  fundingRate: number;
};

export type ChartSeriesMode = "line" | "step-before";

export type ChartSeriesInput = {
  label: string;
  color: string;
  points: FundingPoint[];
  mode?: ChartSeriesMode;
};
