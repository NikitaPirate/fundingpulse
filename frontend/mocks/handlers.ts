import { http, HttpResponse } from "msw";

import {
  apiUrl,
  buildHistoricalDifferencesFixture,
  buildLiveDifferencesFixture,
  defaultFundingArbitrageFixtures,
} from "./fundingArbitrage";
import {
  buildHistoricalAvgFixture,
  buildHistoricalLatestFixture,
  buildLiveLatestFixture,
} from "./assetFunding";
import {
  buildContractMetaFixture,
  buildContractSearchFixture,
  buildHistoricalPointsFixture,
  buildHistoricalSumsFixture,
  buildLivePointsFixture,
} from "./contractAnalysis";

export const handlers = [
  http.get(apiUrl("/api/v0/meta/assets"), () =>
    HttpResponse.json(defaultFundingArbitrageFixtures.assets),
  ),
  http.get(apiUrl("/api/v0/meta/sections"), () =>
    HttpResponse.json(defaultFundingArbitrageFixtures.sections),
  ),
  http.get(apiUrl("/api/v0/meta/quotes"), () =>
    HttpResponse.json(defaultFundingArbitrageFixtures.quotes),
  ),
  http.get(apiUrl("/api/v0/meta/contracts/search"), ({ request }) =>
    HttpResponse.json(
      buildContractSearchFixture(
        new URL(request.url).searchParams.get("query") ?? "",
        Number.parseInt(new URL(request.url).searchParams.get("limit") ?? "10", 10),
      ),
    ),
  ),
  http.get(apiUrl("/api/v0/meta/contracts/:contract_id"), ({ params }) => {
    const fixture = buildContractMetaFixture(params.contract_id as string);

    if (!fixture) {
      return HttpResponse.json(
        { error: { message: "Contract not found" } },
        { status: 404 },
      );
    }

    return HttpResponse.json(fixture);
  }),
  http.get(apiUrl("/api/v0/funding-data/diff/live_differences"), ({ request }) =>
    HttpResponse.json(buildLiveDifferencesFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/diff/historical_differences"), ({ request }) =>
    HttpResponse.json(buildHistoricalDifferencesFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/live_latest"), ({ request }) =>
    HttpResponse.json(buildLiveLatestFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/historical_latest"), ({ request }) =>
    HttpResponse.json(buildHistoricalLatestFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/historical_avg"), ({ request }) =>
    HttpResponse.json(buildHistoricalAvgFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/historical_sums"), ({ request }) =>
    HttpResponse.json(buildHistoricalSumsFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/live_points"), ({ request }) =>
    HttpResponse.json(buildLivePointsFixture(new URL(request.url).searchParams)),
  ),
  http.get(apiUrl("/api/v0/funding-data/historical_points"), ({ request }) =>
    HttpResponse.json(buildHistoricalPointsFixture(new URL(request.url).searchParams)),
  ),
];
