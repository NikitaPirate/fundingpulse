import type { paths } from "../_generated/api-types";

export type MetaAssetsResponse =
  paths["/api/v0/meta/assets"]["get"]["responses"][200]["content"]["application/json"];

export type MetaSectionsResponse =
  paths["/api/v0/meta/sections"]["get"]["responses"][200]["content"]["application/json"];

export type MetaQuotesResponse =
  paths["/api/v0/meta/quotes"]["get"]["responses"][200]["content"]["application/json"];

export type LiveDifferencesResponse =
  paths["/api/v0/funding-data/diff/live_differences"]["get"]["responses"][200]["content"]["application/json"];

export type LiveDifferenceRow = LiveDifferencesResponse["data"][number];

export type HistoricalDifferencesResponse =
  paths["/api/v0/funding-data/diff/historical_differences"]["get"]["responses"][200]["content"]["application/json"];

export type HistoricalDifferenceRow = HistoricalDifferencesResponse["data"][number];

export type LiveLatestResponse =
  paths["/api/v0/funding-data/live_latest"]["get"]["responses"][200]["content"]["application/json"];

export type LiveLatestRow = LiveLatestResponse[number];

export type HistoricalLatestResponse =
  paths["/api/v0/funding-data/historical_latest"]["get"]["responses"][200]["content"]["application/json"];

export type HistoricalLatestRow = HistoricalLatestResponse[number];

export type HistoricalAvgResponse =
  paths["/api/v0/funding-data/historical_avg"]["get"]["responses"][200]["content"]["application/json"];

export type HistoricalAvgEntry = HistoricalAvgResponse[number];

export type HistoricalSumsResponse =
  paths["/api/v0/funding-data/historical_sums"]["get"]["responses"][200]["content"]["application/json"];

export type HistoricalSumsEntry = HistoricalSumsResponse[number];

export type FundingPointResponse =
  paths["/api/v0/funding-data/live_points"]["get"]["responses"][200]["content"]["application/json"];

export type FundingPointEntry = FundingPointResponse[number];

export type ContractSearchResponse =
  paths["/api/v0/meta/contracts/search"]["get"]["responses"][200]["content"]["application/json"];

export type ContractMetaResponse =
  paths["/api/v0/meta/contracts/{contract_id}"]["get"]["responses"][200]["content"]["application/json"];
