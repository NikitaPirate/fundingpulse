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
];
