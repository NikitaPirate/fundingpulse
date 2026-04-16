"use client";

import { useState } from "react";

import type { ContractMeta, FundingPoint } from "../../_lib/types";
import { FundingChart, buildSpreadSeries } from "./FundingChart";
import { SpreadToggle } from "./SpreadToggle";

type LiveFundingChartProps = {
  c1Meta: ContractMeta | null;
  c2Meta: ContractMeta | null;
  c1Points: FundingPoint[];
  c2Points: FundingPoint[];
  loading: boolean;
  error: string | null;
  pairMode: boolean;
};

export function LiveFundingChart({
  c1Meta,
  c2Meta,
  c1Points,
  c2Points,
  loading,
  error,
  pairMode,
}: LiveFundingChartProps) {
  const [displayMode, setDisplayMode] = useState<"individual" | "spread">("individual");

  const series = [
    ...(c1Meta
      ? [
          {
            label: `${c1Meta.sectionName} / ${c1Meta.quoteName}`,
            color: "primary",
            points: c1Points,
          },
        ]
      : []),
    ...(c2Meta
      ? [
          {
            label: `${c2Meta.sectionName} / ${c2Meta.quoteName}`,
            color: "secondary",
            points: c2Points,
          },
        ]
      : []),
  ];

  const resolvedSeries =
    pairMode && displayMode === "spread" && series.length === 2
      ? [buildSpreadSeries(series[0], series[1])]
      : series;

  return (
    <>
      {pairMode ? <SpreadToggle onChange={setDisplayMode} value={displayMode} /> : null}
      <FundingChart
        defaultVisibleDays={7}
        emptyMessage="No live funding points for the selected contract window."
        error={error}
        loading={loading}
        series={resolvedSeries}
      />
    </>
  );
}
