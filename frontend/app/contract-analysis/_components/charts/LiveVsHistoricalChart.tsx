"use client";

import type { ContractMeta, FundingPoint } from "../../_lib/types";
import { FundingChart } from "./FundingChart";

type LiveVsHistoricalChartProps = {
  meta: ContractMeta | null;
  livePoints: FundingPoint[];
  historicalPoints: FundingPoint[];
  liveLoading: boolean;
  historicalLoading: boolean;
  liveError: string | null;
  historicalError: string | null;
};

export function LiveVsHistoricalChart({
  meta,
  livePoints,
  historicalPoints,
  liveLoading,
  historicalLoading,
  liveError,
  historicalError,
}: LiveVsHistoricalChartProps) {
  const label = meta ? `${meta.sectionName} / ${meta.quoteName}` : "Contract";

  return (
    <FundingChart
      emptyMessage="No overlapping live or historical points for this contract."
      error={liveError ?? historicalError}
      loading={liveLoading || historicalLoading}
      series={[
        {
          label: `${label} live`,
          color: "primary",
          points: livePoints,
        },
        {
          label: `${label} historical`,
          color: "secondary",
          mode: "step-before",
          points: historicalPoints,
        },
      ]}
    />
  );
}
