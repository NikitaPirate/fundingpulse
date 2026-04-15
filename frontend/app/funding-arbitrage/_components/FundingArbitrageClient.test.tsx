import type { AnchorHTMLAttributes, ReactNode } from "react";

import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { server } from "../../../mocks/node";
import {
  apiUrl,
  buildLiveDifferencesResponse,
  defaultFundingArbitrageFixtures,
} from "../../../mocks/fundingArbitrage";
import { FundingArbitrageClient } from "./FundingArbitrageClient";

let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/funding-arbitrage",
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

describe("FundingArbitrageClient", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    window.history.replaceState({}, "", "http://localhost:3000/funding-arbitrage");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders ranked pairs from the shared contract mocks", async () => {
    render(<FundingArbitrageClient />);

    const opportunitiesRegion = await screen.findByRole("region", {
      name: "Funding arbitrage opportunities",
    });
    const pairLinks = within(opportunitiesRegion).getAllByRole("link");

    expect(pairLinks).toHaveLength(2);
    expect(pairLinks[0]).toHaveTextContent("BTC");
    expect(pairLinks[0]).toHaveTextContent("binance_usd-m");
    expect(pairLinks[0]).toHaveTextContent("bybit");
    expect(pairLinks[1]).toHaveTextContent("ETH");
    expect(pairLinks[1]).toHaveTextContent("okx");
    expect(pairLinks[1]).toHaveTextContent("bybit");
  });

  test("shows empty state when the API returns no matches", async () => {
    server.use(
      http.get(apiUrl("/api/v0/funding-data/diff/live_differences"), () =>
        HttpResponse.json(
          buildLiveDifferencesResponse([], {
            total_count: 0,
            limit: 20,
            has_more: false,
          }),
        ),
      ),
    );

    render(<FundingArbitrageClient />);

    expect(await screen.findByText("No pairs match the current filters.")).toBeInTheDocument();
  });

  test("shows API errors from the fetch layer", async () => {
    server.use(
      http.get(apiUrl("/api/v0/funding-data/diff/live_differences"), () =>
        HttpResponse.json(
          {
            error: {
              message: "Funding diff backend is unavailable",
            },
          },
          { status: 500 },
        ),
      ),
    );

    render(<FundingArbitrageClient />);

    expect(
      await screen.findByText(
        "Failed to load funding arbitrage data: Funding diff backend is unavailable",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Filters")).toBeInTheDocument();
    expect(defaultFundingArbitrageFixtures.assets.data.names.length).toBeGreaterThan(0);
  });
});
