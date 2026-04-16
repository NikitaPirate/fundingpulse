import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { ChartSeriesInput } from "../../_lib/types";
import { FundingChart } from "./FundingChart";

class MockUPlot {
  static instances: MockUPlot[] = [];
  static paths = {
    stepped: () => undefined,
  };

  root: HTMLElement;
  data: Array<Array<number | null>>;
  scales = { x: { min: 0, max: 0 } };
  cursor = { top: 0, idx: null as number | null, idxs: [] as Array<number | null> };
  lastScaleUpdate: { key: string; min: number; max: number } | null = null;

  constructor(
    _options: unknown,
    data: Array<Array<number | null>>,
    host: HTMLElement,
  ) {
    this.data = data;
    this.root = document.createElement("div");
    this.root.className = "uplot";
    this.root.appendChild(document.createElement("div")).className = "u-over";
    this.root.appendChild(document.createElement("div")).className = "u-axis";
    host.appendChild(this.root);

    const xValues = data[0] as number[];
    this.scales.x.min = xValues[0] ?? 0;
    this.scales.x.max = xValues[xValues.length - 1] ?? 0;
    MockUPlot.instances.push(this);
  }

  destroy() {
    this.root.remove();
  }

  posToVal(position: number) {
    return position;
  }

  setCursor() {}

  setData(data: Array<Array<number | null>>) {
    this.data = data;
  }

  setScale(key: string, value: { min: number; max: number }) {
    this.lastScaleUpdate = { key, ...value };
    this.scales.x.min = value.min;
    this.scales.x.max = value.max;
  }

  setSize() {}
}

vi.mock("uplot", () => ({
  default: MockUPlot,
}));

const series: ChartSeriesInput[] = [
  {
    label: "binance_usd-m / USDT",
    color: "primary",
    points: [
      {
        contractId: "btc-binance_usd-m-usdt",
        timestamp: 1_776_337_846,
        fundingRate: 0.0321,
      },
      {
        contractId: "btc-binance_usd-m-usdt",
        timestamp: 1_776_338_146,
        fundingRate: 0.0284,
      },
    ],
  },
];

describe("FundingChart", () => {
  const originalResizeObserver = globalThis.ResizeObserver;
  const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

  beforeEach(() => {
    MockUPlot.instances = [];
    HTMLElement.prototype.getBoundingClientRect = vi.fn(() => ({
      width: 960,
      height: 320,
      top: 0,
      right: 960,
      bottom: 320,
      left: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    })) as typeof HTMLElement.prototype.getBoundingClientRect;

    globalThis.ResizeObserver = class {
      private readonly callback: ResizeObserverCallback;

      constructor(callback: ResizeObserverCallback) {
        this.callback = callback;
      }

      observe(target: Element) {
        this.callback(
          [
            {
              target,
              contentRect: target.getBoundingClientRect(),
            } as ResizeObserverEntry,
          ],
          this as unknown as ResizeObserver,
        );
      }

      disconnect() {}

      unobserve() {}
    } as typeof ResizeObserver;
  });

  afterEach(() => {
    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
    globalThis.ResizeObserver = originalResizeObserver;
  });

  test("mounts uPlot after loading resolves", async () => {
    const { container, rerender } = render(
      <FundingChart
        emptyMessage="No data."
        loading
        series={series}
      />,
    );

    expect(screen.getByText("Loading chart…")).toBeInTheDocument();

    rerender(
      <FundingChart
        emptyMessage="No data."
        loading={false}
        series={series}
      />,
    );

    await waitFor(() => {
      expect(container.querySelector(".uplot")).toBeInTheDocument();
    });
  });

  test("applies a trailing default x window when data spans longer than requested", async () => {
    const longRangeSeries: ChartSeriesInput[] = [
      {
        label: "binance_usd-m / USDT",
        color: "primary",
        points: [
          {
            contractId: "btc-binance_usd-m-usdt",
            timestamp: 1_700_000_000,
            fundingRate: 0.0321,
          },
          {
            contractId: "btc-binance_usd-m-usdt",
            timestamp: 1_707_776_000,
            fundingRate: 0.0284,
          },
        ],
      },
    ];

    render(
      <FundingChart
        defaultVisibleDays={14}
        emptyMessage="No data."
        loading={false}
        series={longRangeSeries}
      />,
    );

    await waitFor(() => {
      expect(MockUPlot.instances).toHaveLength(1);
      expect(MockUPlot.instances[0]?.lastScaleUpdate).toEqual({
        key: "x",
        min: 1_706_566_400,
        max: 1_707_776_000,
      });
    });
  });
});
