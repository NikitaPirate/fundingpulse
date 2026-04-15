export type Normalization = "raw" | "1h" | "8h" | "1d" | "365d";

export type PeriodPreset = "8h" | "1d" | "3d" | "7d" | "14d" | "30d" | "90d";

export type PeriodState =
  | {
      type: "live";
      label: "Live";
    }
  | {
      type: "preset";
      preset: PeriodPreset;
      label: string;
    }
  | {
      type: "custom";
      fromDate: string;
      toDate: string;
      label: string;
    };

export type FilterOption = {
  value: string;
  label: string;
};

export type FundingArbitrageFilters = {
  assets: string[];
  sections: string[];
  quotes: string[];
  compareFor: string | null;
  period: PeriodState;
  normalize: Normalization;
  minDiff: number | null;
  offset: number;
  limit: number;
};

export type FundingArbitrageMeta = {
  assets: FilterOption[];
  sections: FilterOption[];
  quotes: FilterOption[];
};

export type ContractSide = {
  id: string;
  section: string;
  quote: string;
  metric: number;
};

type BaseFundingArbitrageRow = {
  assetName: string;
  contract1: ContractSide;
  contract2: ContractSide;
  difference: number;
  absDifference: number;
};

export type FundingArbitrageRow =
  | (BaseFundingArbitrageRow & {
      kind: "live";
    })
  | (BaseFundingArbitrageRow & {
      kind: "historical";
      alignedFrom: number;
      alignedTo: number;
    });

export type FundingArbitrageResponse = {
  data: FundingArbitrageRow[];
  totalCount: number;
  offset: number;
  limit: number;
  hasMore: boolean;
};
