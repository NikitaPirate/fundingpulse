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
