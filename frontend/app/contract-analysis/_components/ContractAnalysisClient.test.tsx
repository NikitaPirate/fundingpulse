import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { formatFundingValue } from "../../_lib/formatFundingValue";
import {
  buildHistoricalLatestFixture,
  buildLiveLatestFixture,
} from "../../../mocks/assetFunding";
import { buildHistoricalSumsFixture } from "../../../mocks/contractAnalysis";
import { ContractAnalysisClient } from "./ContractAnalysisClient";

let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/contract-analysis",
  useSearchParams: () => currentSearchParams,
}));

describe("ContractAnalysisClient", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    window.history.replaceState({}, "", "http://localhost:3000/contract-analysis");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  test("renders quiet zero state without selected contracts", async () => {
    render(<ContractAnalysisClient />);

    expect(
      await screen.findByText(
        "Search for a contract to begin analysis. Charts stay visible below and will fill in as soon as you pick a contract.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Summary will appear after you choose one or two contracts."),
    ).toBeInTheDocument();
    expect(screen.getByText("Live Funding Rates")).toBeInTheDocument();
    expect(screen.getByText("Historical Funding Rates")).toBeInTheDocument();
  });

  test("renders single-contract summary for a direct contract entry", async () => {
    currentSearchParams = new URLSearchParams([["c1", "btc-bybit-usdt"]]);

    const sliceParams = new URLSearchParams([
      ["asset_names", "BTC"],
      ["section_names", "bybit"],
      ["quote_names", "USDT"],
      ["normalize_to_interval", "365d"],
    ]);

    const liveRow = buildLiveLatestFixture(sliceParams).find(
      (row) => row.contract_id === "btc-bybit-usdt",
    );
    const settledRow = buildHistoricalLatestFixture(sliceParams).find(
      (row) => row.contract_id === "btc-bybit-usdt",
    );
    const sumsRow = buildHistoricalSumsFixture(
      new URLSearchParams([
        ...sliceParams.entries(),
        ["windows", "7"],
        ["windows", "14"],
        ["windows", "30"],
        ["windows", "90"],
        ["windows", "180"],
        ["windows", "365"],
      ]),
    ).find((row) => row.contract_id === "btc-bybit-usdt");

    render(<ContractAnalysisClient />);

    const summaryRegion = await screen.findByRole("region", {
      name: "Contract analysis summary",
    });

    await waitFor(() => {
      expect(summaryRegion).toHaveTextContent("bybit / USDT");
      expect(summaryRegion).toHaveTextContent(formatFundingValue(liveRow?.funding_rate ?? 0));
      expect(summaryRegion).toHaveTextContent(
        formatFundingValue(settledRow?.funding_rate ?? 0),
      );
      expect(summaryRegion).toHaveTextContent(
        formatFundingValue(sumsRow?.windows[0]?.funding_rate ?? 0),
      );
    });
  });

  test("renders pair spread summary and chart sections from paired URL state", async () => {
    currentSearchParams = new URLSearchParams([
      ["c1", "btc-binance_usd-m-usdc"],
      ["c2", "btc-bybit-usdc"],
    ]);

    const c1Params = new URLSearchParams([
      ["asset_names", "BTC"],
      ["section_names", "binance_usd-m"],
      ["quote_names", "USDC"],
      ["normalize_to_interval", "365d"],
    ]);
    const c2Params = new URLSearchParams([
      ["asset_names", "BTC"],
      ["section_names", "bybit"],
      ["quote_names", "USDC"],
      ["normalize_to_interval", "365d"],
    ]);

    const c1Live = buildLiveLatestFixture(c1Params).find(
      (row) => row.contract_id === "btc-binance_usd-m-usdc",
    );
    const c2Live = buildLiveLatestFixture(c2Params).find(
      (row) => row.contract_id === "btc-bybit-usdc",
    );
    const expectedSpread = (c1Live?.funding_rate ?? 0) - (c2Live?.funding_rate ?? 0);

    render(<ContractAnalysisClient />);

    const summaryRegion = await screen.findByRole("region", {
      name: "Contract analysis summary",
    });

    await waitFor(() => {
      expect(summaryRegion).toHaveTextContent("Contract 1");
      expect(summaryRegion).toHaveTextContent("Contract 2");
      expect(summaryRegion).toHaveTextContent("Spread");
      expect(summaryRegion).toHaveTextContent(formatFundingValue(expectedSpread));
    });

    expect(screen.getByText("Live Funding Rates")).toBeInTheDocument();
    expect(screen.getByText("Historical Funding Rates")).toBeInTheDocument();
    expect(screen.getByText("Live vs Historical")).toBeInTheDocument();
  });

  test("search selection updates the URL state", async () => {
    render(<ContractAnalysisClient />);

    fireEvent.click(screen.getByRole("button", { name: /Contract 1/i }));
    fireEvent.change(screen.getByPlaceholderText("Search asset, exchange, or quote..."), {
      target: { value: "btc bybit" },
    });

    await new Promise((resolve) => window.setTimeout(resolve, 350));

    fireEvent.click(await screen.findByRole("button", { name: /BTC \/ bybit \/ USDT/i }));

    expect(window.location.search).toContain("c1=btc-bybit-usdt");
  });

  test("normalization control updates the URL state", async () => {
    currentSearchParams = new URLSearchParams([["c1", "btc-bybit-usdt"]]);

    render(<ContractAnalysisClient />);

    fireEvent.click(screen.getByRole("button", { name: /Normalization/i }));
    fireEvent.click(await screen.findByLabelText("1 Day"));

    expect(window.location.search).toContain("normalize=1d");
  });

  test("swap button rewrites the pair order in URL state", async () => {
    currentSearchParams = new URLSearchParams([
      ["c1", "btc-binance_usd-m-usdt"],
      ["c2", "btc-bybit-usdt"],
    ]);

    render(<ContractAnalysisClient />);

    const selectionRegion = await screen.findByRole("region", {
      name: "Contract analysis selection",
    });
    fireEvent.click(within(selectionRegion).getByRole("button", { name: "Swap order" }));

    expect(window.location.search).toContain("c1=btc-bybit-usdt");
    expect(window.location.search).toContain("c2=btc-binance_usd-m-usdt");
  });
});
