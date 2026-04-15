import type { ReadonlyURLSearchParams } from "next/navigation";

import type {
  AssetFundingFilters,
  Normalization,
  SortDirection,
  SortField,
} from "./types";

const NORMALIZATIONS = new Set<Normalization>(["raw", "1h", "8h", "1d", "365d"]);
const SORT_FIELDS = new Set<SortField>([
  "section",
  "quote",
  "live",
  "lastSettled",
  "avg7d",
  "avg30d",
  "avg90d",
]);
const SORT_DIRECTIONS = new Set<SortDirection>(["asc", "desc"]);

export const DEFAULT_FILTERS: AssetFundingFilters = {
  asset: null,
  sections: [],
  quotes: [],
  normalize: "365d",
  sortBy: "live",
  sortDir: "desc",
};

export function parseFilters(
  searchParams: ReadonlyURLSearchParams,
): AssetFundingFilters {
  const normalize = searchParams.get("normalize");
  const sortBy = searchParams.get("sort");
  const sortDir = searchParams.get("dir");

  return {
    asset: searchParams.get("asset") || null,
    sections: searchParams.getAll("sections").filter(Boolean),
    quotes: searchParams.getAll("quotes").filter(Boolean),
    normalize:
      normalize && NORMALIZATIONS.has(normalize as Normalization)
        ? (normalize as Normalization)
        : DEFAULT_FILTERS.normalize,
    sortBy:
      sortBy && SORT_FIELDS.has(sortBy as SortField)
        ? (sortBy as SortField)
        : DEFAULT_FILTERS.sortBy,
    sortDir:
      sortDir && SORT_DIRECTIONS.has(sortDir as SortDirection)
        ? (sortDir as SortDirection)
        : DEFAULT_FILTERS.sortDir,
  };
}

export function serializeFilters(filters: AssetFundingFilters) {
  const params = new URLSearchParams();

  if (filters.asset) {
    params.set("asset", filters.asset);
  }

  for (const section of filters.sections) {
    params.append("sections", section);
  }

  for (const quote of filters.quotes) {
    params.append("quotes", quote);
  }

  if (filters.normalize !== DEFAULT_FILTERS.normalize) {
    params.set("normalize", filters.normalize);
  }

  if (filters.sortBy !== DEFAULT_FILTERS.sortBy) {
    params.set("sort", filters.sortBy);
  }

  if (filters.sortDir !== DEFAULT_FILTERS.sortDir) {
    params.set("dir", filters.sortDir);
  }

  return params;
}

export function serializeFetchFilters(filters: AssetFundingFilters) {
  const params = new URLSearchParams();

  if (filters.asset) {
    params.set("asset", filters.asset);
  }

  for (const section of filters.sections) {
    params.append("sections", section);
  }

  for (const quote of filters.quotes) {
    params.append("quotes", quote);
  }

  params.set("normalize", filters.normalize);

  return params.toString();
}
