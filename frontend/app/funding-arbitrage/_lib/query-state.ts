import type { ReadonlyURLSearchParams } from "next/navigation";

import type {
  FundingArbitrageFilters,
  Normalization,
  PeriodPreset,
  PeriodState,
} from "./types";

const NORMALIZATIONS = new Set<Normalization>(["raw", "1h", "8h", "1d", "365d"]);
const PERIOD_PRESET_LABELS: Record<PeriodPreset, string> = {
  "8h": "8 Hours",
  "1d": "1 Day",
  "3d": "3 Days",
  "7d": "7 Days",
  "14d": "14 Days",
  "30d": "30 Days",
  "90d": "90 Days",
};

export const DEFAULT_LIMIT = 20;

export const DEFAULT_FILTERS: FundingArbitrageFilters = {
  assets: [],
  sections: [],
  quotes: [],
  compareFor: null,
  period: { type: "live", label: "Live" },
  normalize: "365d",
  minDiff: null,
  offset: 0,
  limit: DEFAULT_LIMIT,
};

function parseBoundedInteger(
  rawValue: string | null,
  fallback: number,
  min: number,
  max: number,
) {
  if (!rawValue) {
    return fallback;
  }

  const parsed = Number.parseInt(rawValue, 10);
  if (Number.isNaN(parsed)) {
    return fallback;
  }

  return Math.min(Math.max(parsed, min), max);
}

function parsePeriod(rawValue: string | null): PeriodState {
  if (!rawValue || rawValue === "live") {
    return DEFAULT_FILTERS.period;
  }

  if (rawValue in PERIOD_PRESET_LABELS) {
    const preset = rawValue as PeriodPreset;
    return {
      type: "preset",
      preset,
      label: PERIOD_PRESET_LABELS[preset],
    };
  }

  const customMatch = rawValue.match(/^(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})$/);
  if (!customMatch) {
    return DEFAULT_FILTERS.period;
  }

  const [, fromDate, toDate] = customMatch;
  return createCustomPeriod(fromDate, toDate);
}

export function createCustomPeriod(fromDate: string, toDate: string): PeriodState {
  return {
    type: "custom",
    fromDate,
    toDate,
    label: `${fromDate} - ${toDate}`,
  };
}

export function parseFilters(
  searchParams: ReadonlyURLSearchParams,
): FundingArbitrageFilters {
  const normalize = searchParams.get("normalize");
  const minDiffRaw = searchParams.get("min_diff");
  const minDiff = minDiffRaw === null ? Number.NaN : Number.parseFloat(minDiffRaw);

  return {
    assets: searchParams.getAll("assets").filter(Boolean),
    sections: searchParams.getAll("sections").filter(Boolean),
    quotes: searchParams.getAll("quotes").filter(Boolean),
    compareFor: searchParams.get("compareFor") || null,
    period: parsePeriod(searchParams.get("period")),
    normalize:
      normalize && NORMALIZATIONS.has(normalize as Normalization)
        ? (normalize as Normalization)
        : DEFAULT_FILTERS.normalize,
    minDiff: Number.isFinite(minDiff) && minDiff >= 0 ? minDiff : null,
    offset: parseBoundedInteger(searchParams.get("offset"), 0, 0, Number.MAX_SAFE_INTEGER),
    limit: parseBoundedInteger(searchParams.get("limit"), DEFAULT_LIMIT, 1, 100),
  };
}

export function serializeFilters(filters: FundingArbitrageFilters) {
  const params = new URLSearchParams();

  for (const asset of filters.assets) {
    params.append("assets", asset);
  }

  for (const section of filters.sections) {
    params.append("sections", section);
  }

  for (const quote of filters.quotes) {
    params.append("quotes", quote);
  }

  if (filters.compareFor) {
    params.set("compareFor", filters.compareFor);
  }

  const serializedPeriod = serializePeriod(filters.period);
  if (serializedPeriod !== "live") {
    params.set("period", serializedPeriod);
  }

  if (filters.normalize !== DEFAULT_FILTERS.normalize) {
    params.set("normalize", filters.normalize);
  }

  if (filters.minDiff !== null) {
    params.set("min_diff", filters.minDiff.toString());
  }

  if (filters.offset > 0) {
    params.set("offset", filters.offset.toString());
  }

  if (filters.limit !== DEFAULT_LIMIT) {
    params.set("limit", filters.limit.toString());
  }

  return params;
}

export function serializePeriod(period: PeriodState) {
  if (period.type === "live") {
    return "live";
  }

  if (period.type === "preset") {
    return period.preset;
  }

  return `${period.fromDate}_${period.toDate}`;
}

export function periodToApiRange(period: PeriodState) {
  if (period.type === "live") {
    return null;
  }

  if (period.type === "preset") {
    const now = Date.now();
    const presetHours: Record<PeriodPreset, number> = {
      "8h": 8,
      "1d": 24,
      "3d": 72,
      "7d": 168,
      "14d": 336,
      "30d": 720,
      "90d": 2160,
    };

    return {
      fromTs: Math.floor((now - presetHours[period.preset] * 60 * 60 * 1000) / 1000),
      toTs: Math.floor(now / 1000),
    };
  }

  return {
    fromTs: Math.floor(new Date(period.fromDate).getTime() / 1000),
    toTs: Math.floor(new Date(period.toDate).getTime() / 1000),
  };
}
