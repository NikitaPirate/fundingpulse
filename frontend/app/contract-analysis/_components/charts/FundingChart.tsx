"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type uPlot from "uplot";

import {
  alignFundingSeries,
  computeSpreadSeries,
  latestNonNullIndices,
} from "../../_lib/chart-data";
import type { ChartSeriesInput } from "../../_lib/types";
import styles from "./FundingChart.module.css";

type ThemeColors = {
  primary: string;
  secondary: string;
  spread: string;
  textMuted: string;
  textSoft: string;
  border: string;
  borderStrong: string;
  grid: string;
};

type FundingChartProps = {
  series: ChartSeriesInput[];
  loading?: boolean;
  error?: string | null;
  emptyMessage: string;
  height?: number;
  defaultVisibleDays?: number;
};

const SECONDS_PER_DAY = 24 * 60 * 60;

function getThemeColors(): ThemeColors {
  const computed = getComputedStyle(document.documentElement);

  return {
    primary: computed.getPropertyValue("--color-chart-primary").trim(),
    secondary: computed.getPropertyValue("--color-chart-secondary").trim(),
    spread: computed.getPropertyValue("--color-chart-spread").trim(),
    textMuted: computed.getPropertyValue("--color-text-muted").trim(),
    textSoft: computed.getPropertyValue("--color-text-soft").trim(),
    border: computed.getPropertyValue("--color-border").trim(),
    borderStrong: computed.getPropertyValue("--color-border-strong").trim(),
    grid: computed.getPropertyValue("--color-grid-line").trim(),
  };
}

function resolveColor(token: string, themeColors: ThemeColors) {
  if (token === "primary" || token === "secondary" || token === "spread") {
    return themeColors[token];
  }

  return token;
}

function formatPercentSmart(value: number) {
  const absoluteValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (absoluteValue >= 1_000_000) {
    const compact = absoluteValue / 1_000_000;
    return `${sign}${compact.toFixed(absoluteValue >= 10_000_000 ? 0 : 1)}M%`;
  }

  if (absoluteValue >= 1_000) {
    const compact = absoluteValue / 1_000;
    return `${sign}${compact.toFixed(absoluteValue >= 100_000 ? 0 : 1)}K%`;
  }

  if (absoluteValue >= 100) {
    return `${value.toFixed(0)}%`;
  }

  if (absoluteValue >= 10) {
    return `${value.toFixed(1)}%`;
  }

  if (absoluteValue >= 1) {
    return `${value.toFixed(2)}%`;
  }

  return `${value.toFixed(3)}%`;
}

function formatAxisTimestamp(timestamp: number, rangeSeconds: number) {
  if (rangeSeconds < 60 * 60) {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(timestamp * 1000);
  }

  const date = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(timestamp * 1000);
  const time = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp * 1000);

  return rangeSeconds >= 3 * 24 * 60 * 60 ? date : `${date}\n${time}`;
}

function attachInteractions(chart: uPlot) {
  const root = chart.root as HTMLElement;
  const over = root.querySelector(".u-over") as HTMLElement | null;

  if (!over) {
    return () => {};
  }

  const xAxis = [...root.querySelectorAll(".u-axis")].reduce<HTMLElement | null>(
    (found, element) => {
      const candidate = element as HTMLElement;
      if (!found) {
        return candidate;
      }

      return candidate.getBoundingClientRect().top > found.getBoundingClientRect().top
        ? candidate
        : found;
    },
    null,
  );

  const previousOverCursor = over.style.cursor;
  const previousAxisCursor = xAxis?.style.cursor;
  over.style.cursor = "ew-resize";
  if (xAxis) {
    xAxis.style.cursor = "col-resize";
  }

  let panning = false;
  let panStartLeft = 0;
  let panStartRect: DOMRect | null = null;
  let panStartMin = 0;
  let panStartMax = 0;

  const onMouseDown = (event: MouseEvent) => {
    if (event.button !== 0) {
      return;
    }

    event.preventDefault();
    panning = true;
    panStartRect = over.getBoundingClientRect();
    panStartLeft = event.clientX - panStartRect.left;
    panStartMin = (chart.scales.x.min as number) ?? 0;
    panStartMax = (chart.scales.x.max as number) ?? 0;
  };

  const onMouseMove = (event: MouseEvent) => {
    if (!panning || !panStartRect) {
      return;
    }

    const nextLeft = event.clientX - panStartRect.left;
    const startValue = chart.posToVal(panStartLeft, "x");
    const nextValue = chart.posToVal(nextLeft, "x");
    const delta = startValue - nextValue;

    chart.setScale("x", {
      min: panStartMin + delta,
      max: panStartMax + delta,
    });
  };

  const onMouseUp = () => {
    panning = false;
    panStartRect = null;
  };

  const onDoubleClick = () => {
    const xValues = chart.data[0] as number[];
    if (xValues.length > 1) {
      chart.setScale("x", {
        min: xValues[0],
        max: xValues[xValues.length - 1],
      });
    }
  };

  let axisZooming = false;
  let axisStartX = 0;
  let axisStartMin = 0;
  let axisStartMax = 0;
  let axisStartRange = 0;
  let axisAnchorValue = 0;

  const onAxisDown = (event: MouseEvent) => {
    if (event.button !== 0) {
      return;
    }

    event.preventDefault();
    axisZooming = true;
    axisStartX = event.clientX;
    const overRect = over.getBoundingClientRect();
    const left = event.clientX - overRect.left;
    axisAnchorValue = chart.posToVal(left, "x");
    axisStartMin = (chart.scales.x.min as number) ?? 0;
    axisStartMax = (chart.scales.x.max as number) ?? 0;
    axisStartRange = axisStartMax - axisStartMin;
  };

  const onAxisMove = (event: MouseEvent) => {
    if (!axisZooming) {
      return;
    }

    const delta = event.clientX - axisStartX;
    if (delta === 0) {
      return;
    }

    const scaleFactor = Math.pow(0.98, -delta);
    const nextRange = axisStartRange * scaleFactor;
    const anchorRatio =
      axisStartRange === 0 ? 0.5 : (axisAnchorValue - axisStartMin) / axisStartRange;

    chart.setScale("x", {
      min: axisAnchorValue - anchorRatio * nextRange,
      max: axisAnchorValue + (1 - anchorRatio) * nextRange,
    });
  };

  const onAxisUp = () => {
    axisZooming = false;
  };

  const onWheel = (event: WheelEvent) => {
    event.preventDefault();

    const xValues = chart.data[0] as number[];
    if (xValues.length < 2) {
      return;
    }

    const rect = over.getBoundingClientRect();
    const left = event.clientX - rect.left;
    const anchor = chart.posToVal(left, "x");
    const min = (chart.scales.x.min as number) ?? xValues[0];
    const max = (chart.scales.x.max as number) ?? xValues[xValues.length - 1];
    const range = max - min;
    const ratio = range === 0 ? 0.5 : (anchor - min) / range;
    const factor = event.deltaY > 0 ? 1.12 : 0.9;
    const nextRange = range * factor;

    chart.setScale("x", {
      min: anchor - ratio * nextRange,
      max: anchor + (1 - ratio) * nextRange,
    });
  };

  over.addEventListener("mousedown", onMouseDown, { passive: false });
  window.addEventListener("mousemove", onMouseMove, { passive: true });
  window.addEventListener("mouseup", onMouseUp, { passive: true });
  over.addEventListener("dblclick", onDoubleClick, { passive: true });
  over.addEventListener("wheel", onWheel, { passive: false });

  if (xAxis) {
    xAxis.addEventListener("mousedown", onAxisDown, { passive: false });
    window.addEventListener("mousemove", onAxisMove, { passive: true });
    window.addEventListener("mouseup", onAxisUp, { passive: true });
  }

  const touchPointers = new Map<number, number>();
  const axisPointers = new Map<number, number>();
  let touchZoomActive = false;
  let touchStartRange = 0;
  let touchStartMin = 0;
  let touchStartMax = 0;
  let touchAnchor = 0;
  let touchStartDistance = 0;
  let touchStartCentroid = 0;
  let axisPanActive = false;
  let axisPanStartLeft = 0;
  let axisPanMin = 0;
  let axisPanMax = 0;
  let axisUnitsPerPx = 0;

  const overTouchActionPrevious = over.style.touchAction;
  const axisTouchActionPrevious = xAxis?.style.touchAction;
  over.style.touchAction = "none";
  if (xAxis) {
    xAxis.style.touchAction = "none";
  }

  const getOverRect = () => over.getBoundingClientRect();

  const onOverPointerDown = (event: PointerEvent) => {
    if (event.pointerType !== "touch") {
      return;
    }

    event.preventDefault();
    const rect = getOverRect();
    const x = event.clientX - rect.left;
    touchPointers.set(event.pointerId, x);

    if (touchPointers.size === 2) {
      const [left, right] = [...touchPointers.values()];
      touchZoomActive = true;
      touchStartMin = (chart.scales.x.min as number) ?? 0;
      touchStartMax = (chart.scales.x.max as number) ?? 0;
      touchStartRange = touchStartMax - touchStartMin;
      touchStartCentroid = (left + right) / 2;
      touchStartDistance = Math.max(1, Math.abs(right - left));
      touchAnchor = chart.posToVal(touchStartCentroid, "x");
    } else {
      chart.setCursor({ left: Math.round(x), top: chart.cursor.top ?? 0 });
    }
  };

  const onOverPointerMove = (event: PointerEvent) => {
    if (event.pointerType !== "touch" || !touchPointers.has(event.pointerId)) {
      return;
    }

    const rect = getOverRect();
    const x = event.clientX - rect.left;
    touchPointers.set(event.pointerId, x);

    if (touchPointers.size === 1) {
      chart.setCursor({ left: Math.round(x), top: chart.cursor.top ?? 0 });
      return;
    }

    if (!touchZoomActive) {
      return;
    }

    const [left, right] = [...touchPointers.values()];
    const centroid = (left + right) / 2;
    const distance = Math.max(1, Math.abs(right - left));
    const factor = distance / Math.max(1, touchStartDistance);
    const nextRange = touchStartRange / factor;
    const anchorRatio =
      touchStartRange === 0 ? 0.5 : (touchAnchor - touchStartMin) / touchStartRange;
    const shift = chart.posToVal(touchStartCentroid, "x") - chart.posToVal(centroid, "x");

    chart.setScale("x", {
      min: touchAnchor - anchorRatio * nextRange + shift,
      max: touchAnchor + (1 - anchorRatio) * nextRange + shift,
    });
  };

  const onOverPointerUp = (event: PointerEvent) => {
    if (event.pointerType !== "touch") {
      return;
    }

    touchPointers.delete(event.pointerId);
    if (touchPointers.size < 2) {
      touchZoomActive = false;
    }
  };

  const onAxisPointerDown = (event: PointerEvent) => {
    if (event.pointerType !== "touch") {
      return;
    }

    event.preventDefault();
    const rect = getOverRect();
    const x = event.clientX - rect.left;
    axisPointers.set(event.pointerId, x);

    if (axisPointers.size === 1) {
      axisPanActive = true;
      axisPanStartLeft = x;
      axisPanMin = (chart.scales.x.min as number) ?? 0;
      axisPanMax = (chart.scales.x.max as number) ?? 0;
      axisUnitsPerPx = Math.abs(chart.posToVal(x, "x") - chart.posToVal(x - 1, "x"));
      return;
    }

    if (axisPointers.size === 2) {
      axisPanActive = false;
      const [left, right] = [...axisPointers.values()];
      touchZoomActive = true;
      touchStartMin = (chart.scales.x.min as number) ?? 0;
      touchStartMax = (chart.scales.x.max as number) ?? 0;
      touchStartRange = touchStartMax - touchStartMin;
      touchStartCentroid = (left + right) / 2;
      touchStartDistance = Math.max(1, Math.abs(right - left));
      touchAnchor = chart.posToVal(touchStartCentroid, "x");
    }
  };

  const onAxisPointerMove = (event: PointerEvent) => {
    if (event.pointerType !== "touch" || !axisPointers.has(event.pointerId)) {
      return;
    }

    const rect = getOverRect();
    const x = event.clientX - rect.left;
    axisPointers.set(event.pointerId, x);

    if (axisPointers.size === 1 && axisPanActive) {
      const delta = axisPanStartLeft - x;
      const shift = delta * axisUnitsPerPx;
      chart.setScale("x", {
        min: axisPanMin + shift,
        max: axisPanMax + shift,
      });
      return;
    }

    if (axisPointers.size === 2 && touchZoomActive) {
      const [left, right] = [...axisPointers.values()];
      const distance = Math.max(1, Math.abs(right - left));
      const factor = distance / Math.max(1, touchStartDistance);
      const nextRange = touchStartRange / factor;
      const anchorRatio =
        touchStartRange === 0 ? 0.5 : (touchAnchor - touchStartMin) / touchStartRange;

      chart.setScale("x", {
        min: touchAnchor - anchorRatio * nextRange,
        max: touchAnchor + (1 - anchorRatio) * nextRange,
      });
    }
  };

  const onAxisPointerUp = (event: PointerEvent) => {
    if (event.pointerType !== "touch") {
      return;
    }

    axisPointers.delete(event.pointerId);
    if (axisPointers.size === 0) {
      axisPanActive = false;
    }
    if (axisPointers.size < 2) {
      touchZoomActive = false;
    }
  };

  over.addEventListener("pointerdown", onOverPointerDown, { passive: false });
  over.addEventListener("pointermove", onOverPointerMove, { passive: false });
  over.addEventListener("pointerup", onOverPointerUp, { passive: false });
  over.addEventListener("pointercancel", onOverPointerUp, { passive: false });

  if (xAxis) {
    xAxis.addEventListener("pointerdown", onAxisPointerDown, { passive: false });
    xAxis.addEventListener("pointermove", onAxisPointerMove, { passive: false });
    xAxis.addEventListener("pointerup", onAxisPointerUp, { passive: false });
    xAxis.addEventListener("pointercancel", onAxisPointerUp, { passive: false });
  }

  return () => {
    over.removeEventListener("mousedown", onMouseDown);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
    over.removeEventListener("dblclick", onDoubleClick);
    over.removeEventListener("wheel", onWheel);
    over.removeEventListener("pointerdown", onOverPointerDown);
    over.removeEventListener("pointermove", onOverPointerMove);
    over.removeEventListener("pointerup", onOverPointerUp);
    over.removeEventListener("pointercancel", onOverPointerUp);
    over.style.cursor = previousOverCursor;
    over.style.touchAction = overTouchActionPrevious;

    if (xAxis) {
      xAxis.removeEventListener("mousedown", onAxisDown);
      xAxis.removeEventListener("pointerdown", onAxisPointerDown);
      xAxis.removeEventListener("pointermove", onAxisPointerMove);
      xAxis.removeEventListener("pointerup", onAxisPointerUp);
      xAxis.removeEventListener("pointercancel", onAxisPointerUp);
      xAxis.style.cursor = previousAxisCursor ?? "";
      xAxis.style.touchAction = axisTouchActionPrevious ?? "";
    }

    window.removeEventListener("mousemove", onAxisMove);
    window.removeEventListener("mouseup", onAxisUp);
  };
}

export function FundingChart({
  series,
  loading = false,
  error = null,
  emptyMessage,
  height = 320,
  defaultVisibleDays,
}: FundingChartProps) {
  const [shellElement, setShellElement] = useState<HTMLDivElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<uPlot | null>(null);
  const [width, setWidth] = useState(0);
  const [legendIdxs, setLegendIdxs] = useState<Array<number | null> | null>(null);
  const [mainSeries, setMainSeries] = useState<number | null>(null);
  const [themeVersion, setThemeVersion] = useState(0);

  const alignedData = useMemo(() => alignFundingSeries(series), [series]);
  const lastIdxs = useMemo(() => latestNonNullIndices(alignedData), [alignedData]);

  const hasData = useMemo(
    () =>
      alignedData.length > 1 &&
      alignedData.slice(1).some((entry) =>
        (entry as Array<number | null>).some((value) => value !== null),
      ),
    [alignedData],
  );

  const dataRange = useMemo(() => {
    const xValues = alignedData[0] as number[];
    if (xValues.length === 0) {
      return { min: 0, max: 0 };
    }

    return {
      min: xValues[0],
      max: xValues[xValues.length - 1],
    };
  }, [alignedData]);

  const shellRef = useCallback((node: HTMLDivElement | null) => {
    setShellElement(node);
  }, []);

  useEffect(() => {
    if (!shellElement) {
      setWidth(0);
      return;
    }

    const element = shellElement;
    const updateWidth = () => {
      setWidth(Math.max(0, Math.floor(element.getBoundingClientRect().width)));
    };

    updateWidth();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateWidth);
      return () => window.removeEventListener("resize", updateWidth);
    }

    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, [shellElement]);

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setThemeVersion((current) => current + 1);
    });

    observer.observe(root, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => observer.disconnect();
  }, []);

  const optionsKey = useMemo(
    () =>
      JSON.stringify({
        labels: series.map((entry) => entry.label),
        colors: series.map((entry) => entry.color),
        modes: series.map((entry) => entry.mode ?? "line"),
        themeVersion,
      }),
    [series, themeVersion],
  );

  const dataKey = useMemo(
    () =>
      JSON.stringify({
        xLength: (alignedData[0] as number[]).length,
        xMin: dataRange.min,
        xMax: dataRange.max,
        series: alignedData.slice(1).map((entry) => {
          const values = entry as Array<number | null>;
          return {
            length: values.length,
            first: values.find((value) => value !== null) ?? null,
            last:
              [...values].reverse().find((value) => value !== null) ?? null,
          };
        }),
      }),
    [alignedData, dataRange.max, dataRange.min],
  );

  useEffect(() => {
    let mounted = true;

    async function mountChart() {
      if (!hostRef.current || width === 0 || !hasData) {
        chartRef.current?.destroy();
        chartRef.current = null;
        return;
      }

      const themeColors = getThemeColors();
      const { default: UPlot } = await import("uplot");
      if (!mounted || !hostRef.current) {
        return;
      }

      chartRef.current?.destroy();
      chartRef.current = null;
      hostRef.current.innerHTML = "";

      const rangeSeconds = dataRange.max - dataRange.min;
      const resolvedColors = series.map((entry) => resolveColor(entry.color, themeColors));
      const stepFactory = UPlot.paths?.stepped;
      const options: uPlot.Options = {
        width,
        height,
        padding: [8, 12, 6, width < 480 ? 18 : 24],
        scales: {
          x: {
            time: true,
          },
        },
        axes: [
          {
            stroke: themeColors.textSoft,
            grid: { show: true, stroke: themeColors.grid },
            ticks: { show: true, stroke: themeColors.borderStrong },
            values: (_chart, values) =>
              values.map((value) => formatAxisTimestamp(value, rangeSeconds)),
            space: 110,
          },
          {
            stroke: themeColors.textSoft,
            size: width < 480 ? 56 : 74,
            grid: { show: true, stroke: themeColors.grid },
            ticks: { show: true, stroke: themeColors.borderStrong },
            values: (_chart, values) => values.map((value) => formatPercentSmart(value)),
          },
        ],
        series: [
          { label: "Time" },
          ...series.map((entry, index) => ({
            label: entry.label,
            stroke: resolvedColors[index],
            width: 2,
            spanGaps: true,
            points: { show: false },
            ...(entry.mode === "step-before" && stepFactory
              ? { paths: stepFactory({ align: -1 }) }
              : {}),
          })),
        ],
        legend: { show: false },
        cursor: {
          x: false,
          y: false,
          points: { one: false },
          drag: { x: false, y: false, setScale: false },
          dataIdx: (chart, seriesIndex, closestIndex, xValue) => {
            if (seriesIndex === 0) {
              return closestIndex;
            }

            const values = chart.data[seriesIndex] as Array<number | null>;
            if (!values.length) {
              return null;
            }

            if (values[closestIndex] !== null) {
              return closestIndex;
            }

            const xValues = chart.data[0] as number[];
            let left = closestIndex - 1;
            while (left >= 0 && values[left] === null) {
              left -= 1;
            }

            let right = closestIndex + 1;
            while (right < values.length && values[right] === null) {
              right += 1;
            }

            if (left < 0 && right >= values.length) {
              return null;
            }

            if (left < 0) {
              return right;
            }

            if (right >= values.length) {
              return left;
            }

            return Math.abs(xValue - xValues[left]) <= Math.abs(xValues[right] - xValue)
              ? left
              : right;
          },
        },
        hooks: {
          setCursor: [
            (chart) => {
              const idxs = Array.isArray(chart.cursor?.idxs)
                ? (chart.cursor.idxs as Array<number | null>).slice(1)
                : [];
              const any = idxs.some((value) => value !== null);

              let nextMainSeries: number | null = null;
              const cursorIndex = chart.cursor?.idx as number | null;
              if (any && cursorIndex !== null) {
                for (let seriesIndex = 0; seriesIndex < idxs.length; seriesIndex += 1) {
                  if (idxs[seriesIndex] === cursorIndex) {
                    nextMainSeries = seriesIndex;
                    break;
                  }
                }
              } else {
                let latestSeriesIndex: number | null = null;
                let latestTimestamp = -Infinity;
                const xValues = chart.data[0] as number[];

                for (let seriesIndex = 0; seriesIndex < lastIdxs.length; seriesIndex += 1) {
                  const valueIndex = lastIdxs[seriesIndex];
                  if (valueIndex !== null && xValues[valueIndex] > latestTimestamp) {
                    latestTimestamp = xValues[valueIndex];
                    latestSeriesIndex = seriesIndex;
                  }
                }

                nextMainSeries = latestSeriesIndex;
              }

              setMainSeries(nextMainSeries);
              setLegendIdxs(any ? idxs : null);
            },
          ],
          setData: [
            () => {
              setLegendIdxs(null);
              setMainSeries(null);
            },
          ],
          ready: [
            (chart) => {
              (chart as uPlot & { __cleanup?: () => void }).__cleanup = attachInteractions(chart);
            },
          ],
          destroy: [
            (chart) => {
              (chart as uPlot & { __cleanup?: () => void }).__cleanup?.();
            },
          ],
        },
      };

      const chart = new UPlot(options, alignedData, hostRef.current);
      if (defaultVisibleDays && rangeSeconds > defaultVisibleDays * SECONDS_PER_DAY) {
        chart.setScale("x", {
          min: Math.max(dataRange.min, dataRange.max - defaultVisibleDays * SECONDS_PER_DAY),
          max: dataRange.max,
        });
      }

      chartRef.current = chart;
    }

    void mountChart();

    return () => {
      mounted = false;
    };
  }, [
    alignedData,
    dataRange.max,
    dataRange.min,
    defaultVisibleDays,
    hasData,
    height,
    lastIdxs,
    optionsKey,
    series,
    width,
  ]);

  useEffect(() => {
    if (!chartRef.current || !hasData) {
      return;
    }

    chartRef.current.setData(alignedData);
  }, [alignedData, dataKey, hasData]);

  useEffect(() => {
    if (!chartRef.current || width === 0) {
      return;
    }

    chartRef.current.setSize({
      width,
      height,
    });
  }, [height, width]);

  useEffect(() => {
    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, []);

  const displayIdxs = legendIdxs ?? lastIdxs;
  const xValues = alignedData[0] as number[];
  const defaultMainSeries = useMemo(() => {
    let selected: number | null = null;
    let latestTimestamp = -Infinity;

    for (let seriesIndex = 0; seriesIndex < lastIdxs.length; seriesIndex += 1) {
      const valueIndex = lastIdxs[seriesIndex];
      if (valueIndex !== null && xValues[valueIndex] > latestTimestamp) {
        latestTimestamp = xValues[valueIndex];
        selected = seriesIndex;
      }
    }

    return selected;
  }, [lastIdxs, xValues]);

  const activeMainSeries = mainSeries ?? defaultMainSeries ?? 0;
  const activeTimestampIndex = displayIdxs[activeMainSeries];
  const activeTimestamp =
    activeTimestampIndex !== null && activeTimestampIndex !== undefined
      ? xValues[activeTimestampIndex]
      : null;
  const themeColors = typeof window === "undefined" ? null : getThemeColors();
  const resolvedLegendColors = series.map((entry) =>
    themeColors ? resolveColor(entry.color, themeColors) : entry.color,
  );

  const legendValues = alignedData.slice(1).map((entry, index) => {
    const valueIndex = displayIdxs[index];
    if (valueIndex === null || valueIndex === undefined) {
      return null;
    }

    return (entry as Array<number | null>)[valueIndex];
  });

  const diffAbs =
    legendValues.length === 2 &&
    legendValues[0] !== null &&
    legendValues[1] !== null
      ? Math.abs(legendValues[0] - legendValues[1])
      : null;

  if (loading) {
    return (
      <div className={styles.chartFrame}>
        <div className={styles.chartState}>Loading chart…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.chartFrame}>
        <div className={styles.chartState}>Chart failed to load: {error}</div>
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className={styles.chartFrame}>
        <div className={styles.chartState}>{emptyMessage}</div>
      </div>
    );
  }

  return (
    <div className={styles.chartFrame} ref={shellRef}>
      <div className={styles.chartHost} ref={hostRef} />
      <div className={styles.legend}>
        <div className={styles.legendHeader}>
          {activeTimestamp === null
            ? "Time: —"
            : `Time: ${new Intl.DateTimeFormat(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              }).format(activeTimestamp * 1000)}`}
        </div>
        <div className={styles.legendRows}>
          {series.map((entry, index) => (
            <div className={styles.legendRow} key={entry.label}>
              <span
                className={styles.legendDot}
                style={{ background: resolvedLegendColors[index] }}
              />
              <span className={styles.legendLabel}>{entry.label}</span>
              <span className={styles.legendValue}>
                {legendValues[index] === null ? "—" : formatPercentSmart(legendValues[index])}
              </span>
            </div>
          ))}
          {diffAbs !== null ? (
            <div className={styles.legendRow}>
              <span className={styles.legendLabel}>Diff</span>
              <span className={styles.legendValue}>{formatPercentSmart(diffAbs)}</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function buildSpreadSeries(
  left: ChartSeriesInput,
  right: ChartSeriesInput,
): ChartSeriesInput {
  const aligned = alignFundingSeries([left, right]);
  const spreadValues = computeSpreadSeries(aligned, 1, 2);

  return {
    label: `${left.label} - ${right.label}`,
    color: "spread",
    mode: left.mode ?? right.mode,
    points: (aligned[0] as number[]).flatMap((timestamp, index) => {
      const value = spreadValues[index];
      return value === null
        ? []
        : [
            {
              contractId: `${left.label}-${right.label}`,
              timestamp,
              fundingRate: value / 100,
            },
          ];
    }),
  };
}
