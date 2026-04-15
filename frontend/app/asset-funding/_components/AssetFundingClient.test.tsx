import type { AnchorHTMLAttributes, ReactNode } from "react";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { formatFundingValue } from "../../_lib/formatFundingValue";
import { server } from "../../../mocks/node";
import {
  apiUrl,
  buildHistoricalAvgFixture,
  buildHistoricalLatestFixture,
  buildLiveLatestFixture,
} from "../../../mocks/assetFunding";
import { AssetFundingClient } from "./AssetFundingClient";

let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/asset-funding",
  useSearchParams: () => currentSearchParams,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    children: ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("AssetFundingClient", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    window.history.replaceState({}, "", "http://localhost:3000/asset-funding");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders quiet zero state without a selected asset", async () => {
    render(<AssetFundingClient />);

    expect(
      await screen.findByText(
        "Choose an asset to see contract-level live, settled, and rolling funding context.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Period")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });

  test("renders merged rows and keeps Last settled as a separate sortable column", async () => {
    currentSearchParams = new URLSearchParams([["asset", "BTC"]]);

    render(<AssetFundingClient />);

    const contractsRegion = await screen.findByRole("region", {
      name: "Asset funding contracts",
    });
    const rowLinks = within(contractsRegion).getAllByRole("link");
    const columnButtons = within(contractsRegion).getAllByRole("button");

    expect(rowLinks).toHaveLength(9);
    expect(columnButtons.map((button) => button.textContent?.replace(/[↑↓↕]/g, "").trim())).toEqual([
      "Exchange",
      "Quote",
      "Live",
      "Last settled",
      "7d",
      "30d",
      "90d",
    ]);
  });

  test("filters the contract slice through URL state", async () => {
    currentSearchParams = new URLSearchParams([
      ["asset", "BTC"],
      ["sections", "bybit"],
      ["quotes", "USDC"],
    ]);

    render(<AssetFundingClient />);

    const contractsRegion = await screen.findByRole("region", {
      name: "Asset funding contracts",
    });
    const rowLinks = within(contractsRegion).getAllByRole("link");

    expect(rowLinks).toHaveLength(1);
    expect(rowLinks[0]).toHaveTextContent("bybit");
    expect(rowLinks[0]).toHaveTextContent("USDC");
    expect(screen.getByText("1 contracts")).toBeInTheDocument();
  });

  test("applies normalization consistently across visible funding metrics", async () => {
    currentSearchParams = new URLSearchParams([
      ["asset", "BTC"],
      ["sections", "binance_usd-m"],
      ["quotes", "USDC"],
      ["normalize", "1d"],
    ]);

    const expectedSearchParams = new URLSearchParams([
      ["asset_names", "BTC"],
      ["section_names", "binance_usd-m"],
      ["quote_names", "USDC"],
      ["normalize_to_interval", "1d"],
    ]);
    const expectedLive = buildLiveLatestFixture(expectedSearchParams)[0];
    const expectedSettled = buildHistoricalLatestFixture(expectedSearchParams)[0];
    const expectedAvg = buildHistoricalAvgFixture(
      new URLSearchParams([
        ...expectedSearchParams.entries(),
        ["windows", "7"],
        ["windows", "30"],
        ["windows", "90"],
      ]),
    )[0];

    render(<AssetFundingClient />);

    const contractsRegion = await screen.findByRole("region", {
      name: "Asset funding contracts",
    });

    expect(contractsRegion).toHaveTextContent(
      formatFundingValue(expectedLive.funding_rate ?? 0),
    );
    expect(contractsRegion).toHaveTextContent(
      formatFundingValue(expectedSettled.funding_rate ?? 0),
    );
    expect(contractsRegion).toHaveTextContent(
      formatFundingValue(expectedAvg.windows[0]?.funding_rate ?? 0),
    );
  });

  test("sorts client-side and keeps null values at the end", async () => {
    currentSearchParams = new URLSearchParams([["asset", "BTC"]]);

    server.use(
      http.get(apiUrl("/api/v0/funding-data/live_latest"), () =>
        HttpResponse.json([
          {
            contract_id: "btc-alpha-usdt",
            asset_name: "BTC",
            section_name: "alpha",
            quote_name: "USDT",
            funding_interval: 8,
            funding_rate: null,
            timestamp: null,
          },
          {
            contract_id: "btc-beta-usdt",
            asset_name: "BTC",
            section_name: "beta",
            quote_name: "USDT",
            funding_interval: 8,
            funding_rate: 0.0001,
            timestamp: 1_710_000_000,
          },
        ]),
      ),
      http.get(apiUrl("/api/v0/funding-data/historical_latest"), () =>
        HttpResponse.json([
          {
            contract_id: "btc-alpha-usdt",
            asset_name: "BTC",
            section_name: "alpha",
            quote_name: "USDT",
            funding_interval: 8,
            funding_rate: 0.00005,
            timestamp: 1_709_971_200,
          },
          {
            contract_id: "btc-beta-usdt",
            asset_name: "BTC",
            section_name: "beta",
            quote_name: "USDT",
            funding_interval: 8,
            funding_rate: 0.0002,
            timestamp: 1_709_971_200,
          },
        ]),
      ),
      http.get(apiUrl("/api/v0/funding-data/historical_avg"), () =>
        HttpResponse.json([
          {
            contract_id: "btc-alpha-usdt",
            asset_name: "BTC",
            section_name: "alpha",
            quote_name: "USDT",
            funding_interval: 8,
            windows: [
              {
                days: 7,
                funding_rate: null,
                points_count: 0,
                expected_count: 21,
                oldest_timestamp: null,
              },
              {
                days: 30,
                funding_rate: null,
                points_count: 0,
                expected_count: 90,
                oldest_timestamp: null,
              },
              {
                days: 90,
                funding_rate: null,
                points_count: 0,
                expected_count: 270,
                oldest_timestamp: null,
              },
            ],
          },
          {
            contract_id: "btc-beta-usdt",
            asset_name: "BTC",
            section_name: "beta",
            quote_name: "USDT",
            funding_interval: 8,
            windows: [
              {
                days: 7,
                funding_rate: 0.0003,
                points_count: 21,
                expected_count: 21,
                oldest_timestamp: 1_709_395_200,
              },
              {
                days: 30,
                funding_rate: 0.0004,
                points_count: 90,
                expected_count: 90,
                oldest_timestamp: 1_707_408_000,
              },
              {
                days: 90,
                funding_rate: 0.0005,
                points_count: 270,
                expected_count: 270,
                oldest_timestamp: 1_702_224_000,
              },
            ],
          },
        ]),
      ),
    );

    render(<AssetFundingClient />);

    const contractsRegion = await screen.findByRole("region", {
      name: "Asset funding contracts",
    });
    const liveHeader = within(contractsRegion).getByRole("button", { name: /live/i });

    fireEvent.click(liveHeader);

    const rowLinks = within(contractsRegion).getAllByRole("link");
    expect(rowLinks[0]).toHaveAttribute("href", "/contract-analysis?c1=btc-beta-usdt");
    expect(rowLinks[1]).toHaveAttribute("href", "/contract-analysis?c1=btc-alpha-usdt");
  });

  test("shows backend errors from the merged fetch layer", async () => {
    currentSearchParams = new URLSearchParams([["asset", "BTC"]]);

    server.use(
      http.get(apiUrl("/api/v0/funding-data/live_latest"), () =>
        HttpResponse.json(
          {
            error: {
              message: "Live latest backend is unavailable",
            },
          },
          { status: 500 },
        ),
      ),
    );

    render(<AssetFundingClient />);

    expect(
      await screen.findByText(
        "Failed to load asset funding data: Live latest backend is unavailable",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Filters")).toBeInTheDocument();
  });
});
