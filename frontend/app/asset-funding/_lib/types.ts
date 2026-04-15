import type { FilterOption } from "../../_components/OptionsFilter";

export type Normalization = "raw" | "1h" | "8h" | "1d" | "365d";

export type SortField =
  | "section"
  | "quote"
  | "live"
  | "lastSettled"
  | "avg7d"
  | "avg30d"
  | "avg90d";

export type SortDirection = "asc" | "desc";

export type AssetFundingFilters = {
  asset: string | null;
  sections: string[];
  quotes: string[];
  normalize: Normalization;
  sortBy: SortField;
  sortDir: SortDirection;
};

export type AssetFundingMeta = {
  assets: FilterOption[];
  sections: FilterOption[];
  quotes: FilterOption[];
};

export type AssetFundingRow = {
  contractId: string;
  assetName: string;
  section: string;
  quote: string;
  fundingInterval: number;
  live: number | null;
  lastSettled: number | null;
  avg7d: number | null;
  avg30d: number | null;
  avg90d: number | null;
  liveTimestamp: number | null;
  lastSettledTimestamp: number | null;
};
