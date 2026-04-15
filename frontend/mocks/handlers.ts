import { http, HttpResponse } from "msw";

import { apiUrl, defaultFundingArbitrageFixtures } from "./fundingArbitrage";

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
  http.get(apiUrl("/api/v0/funding-data/diff/live_differences"), () =>
    HttpResponse.json(defaultFundingArbitrageFixtures.live),
  ),
  http.get(apiUrl("/api/v0/funding-data/diff/historical_differences"), () =>
    HttpResponse.json(defaultFundingArbitrageFixtures.historical),
  ),
];
