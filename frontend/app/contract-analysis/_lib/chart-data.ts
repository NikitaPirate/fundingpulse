import type uPlot from "uplot";

import type { ChartSeriesInput } from "./types";

export function alignFundingSeries(series: ChartSeriesInput[]): uPlot.AlignedData {
  const timestamps = new Set<number>();

  for (const entry of series) {
    for (const point of entry.points) {
      timestamps.add(point.timestamp);
    }
  }

  const xValues = [...timestamps].sort((left, right) => left - right);
  const aligned: uPlot.AlignedData = [xValues];

  for (const entry of series) {
    const pointMap = new Map(
      entry.points.map((point) => [point.timestamp, point.fundingRate * 100]),
    );

    aligned.push(
      xValues.map((timestamp) => {
        const value = pointMap.get(timestamp);
        return value ?? null;
      }),
    );
  }

  return aligned;
}

export function latestNonNullIndices(data: uPlot.AlignedData): Array<number | null> {
  const indices: Array<number | null> = [];

  for (let seriesIndex = 1; seriesIndex < data.length; seriesIndex += 1) {
    const values = data[seriesIndex] as Array<number | null>;
    let found: number | null = null;

    for (let valueIndex = values.length - 1; valueIndex >= 0; valueIndex -= 1) {
      if (values[valueIndex] !== null) {
        found = valueIndex;
        break;
      }
    }

    indices.push(found);
  }

  return indices;
}

export function computeSpreadSeries(
  data: uPlot.AlignedData,
  leftIndex: number,
  rightIndex: number,
) {
  const left = data[leftIndex] as Array<number | null>;
  const right = data[rightIndex] as Array<number | null>;

  return left.map((value, index) => {
    const paired = right[index];
    if (value === null || paired === null) {
      return null;
    }

    return value - paired;
  });
}
