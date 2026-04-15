"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { OptionsFilter } from "../../_components/OptionsFilter";
import styles from "../page.module.css";
import { fetchAssetFundingMeta, fetchAssetFundingRows } from "../_lib/api";
import {
  DEFAULT_FILTERS,
  parseFilters,
  serializeFetchFilters,
  serializeFilters,
} from "../_lib/query-state";
import type {
  AssetFundingMeta,
  AssetFundingRow,
  AssetFundingFilters,
  Normalization,
  SortField,
} from "../_lib/types";
import { AssetFundingTable } from "./AssetFundingTable";

const NORMALIZATION_OPTIONS: Array<{ value: Normalization; label: string }> = [
  { value: "raw", label: "Raw" },
  { value: "1h", label: "1 Hour" },
  { value: "8h", label: "8 Hours" },
  { value: "1d", label: "1 Day" },
  { value: "365d", label: "365 Days" },
];

const EMPTY_META: AssetFundingMeta = {
  assets: [],
  sections: [],
  quotes: [],
};

type MetaState = {
  meta: AssetFundingMeta;
  error: string | null;
  settled: boolean;
};

type DataState = {
  rows: AssetFundingRow[] | null;
  error: string | null;
  settledKey: string | null;
};

function compareNullableNumber(
  left: number | null,
  right: number | null,
  direction: AssetFundingFilters["sortDir"],
) {
  if (left === null && right === null) {
    return 0;
  }
  if (left === null) {
    return 1;
  }
  if (right === null) {
    return -1;
  }
  return direction === "asc" ? left - right : right - left;
}

function compareText(
  left: string,
  right: string,
  direction: AssetFundingFilters["sortDir"],
) {
  return direction === "asc"
    ? left.localeCompare(right)
    : right.localeCompare(left);
}

function sortRows(
  rows: AssetFundingRow[] | null,
  sortBy: SortField,
  sortDir: AssetFundingFilters["sortDir"],
) {
  if (!rows) {
    return null;
  }

  return rows.toSorted((left, right) => {
    switch (sortBy) {
      case "section":
        return compareText(left.section, right.section, sortDir);
      case "quote":
        return compareText(left.quote, right.quote, sortDir);
      case "live":
        return compareNullableNumber(left.live, right.live, sortDir);
      case "lastSettled":
        return compareNullableNumber(left.lastSettled, right.lastSettled, sortDir);
      case "avg7d":
        return compareNullableNumber(left.avg7d, right.avg7d, sortDir);
      case "avg30d":
        return compareNullableNumber(left.avg30d, right.avg30d, sortDir);
      case "avg90d":
        return compareNullableNumber(left.avg90d, right.avg90d, sortDir);
    }
  });
}

export function AssetFundingClient() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentQuery = searchParams.toString();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const fetchKey = useMemo(() => serializeFetchFilters(filters), [filters]);
  const [metaState, setMetaState] = useState<MetaState>({
    meta: EMPTY_META,
    error: null,
    settled: false,
  });
  const [dataState, setDataState] = useState<DataState>({
    rows: null,
    error: null,
    settledKey: null,
  });

  const replaceFilters = useCallback(
    (nextFilters: AssetFundingFilters) => {
      const serialized = serializeFilters(nextFilters).toString();
      if (serialized === currentQuery) {
        return;
      }

      const nextUrl = serialized ? `${pathname}?${serialized}` : pathname;
      window.history.replaceState(null, "", nextUrl);
    },
    [currentQuery, pathname],
  );

  function updateFilterPatch(patch: Partial<AssetFundingFilters>) {
    replaceFilters({
      ...filters,
      ...patch,
    });
  }

  function handleSortChange(field: SortField) {
    if (filters.sortBy === field) {
      updateFilterPatch({
        sortDir: filters.sortDir === "asc" ? "desc" : "asc",
      });
      return;
    }

    updateFilterPatch({
      sortBy: field,
      sortDir: field === "section" || field === "quote" ? "asc" : "desc",
    });
  }

  useEffect(() => {
    const abortController = new AbortController();

    fetchAssetFundingMeta(abortController.signal)
      .then((meta) => {
        setMetaState({
          meta,
          error: null,
          settled: true,
        });
      })
      .catch((error: unknown) => {
        if (abortController.signal.aborted) {
          return;
        }

        setMetaState({
          meta: EMPTY_META,
          error: error instanceof Error ? error.message : "Unknown error",
          settled: true,
        });
      });

    return () => abortController.abort();
  }, []);

  useEffect(() => {
    if (!filters.asset) {
      return;
    }

    const abortController = new AbortController();

    fetchAssetFundingRows(filters, abortController.signal)
      .then((rows) => {
        setDataState({
          rows,
          error: null,
          settledKey: fetchKey,
        });
      })
      .catch((error: unknown) => {
        if (abortController.signal.aborted) {
          return;
        }

        setDataState({
          rows: null,
          error: error instanceof Error ? error.message : "Unknown error",
          settledKey: fetchKey,
        });
      });

    return () => abortController.abort();
  }, [fetchKey, filters]);

  const metaLoading = !metaState.settled;
  const metaError = metaState.error;
  const rows =
    filters.asset !== null && dataState.settledKey === fetchKey ? dataState.rows : null;
  const dataError =
    filters.asset !== null && dataState.settledKey === fetchKey ? dataState.error : null;
  const dataLoading = filters.asset !== null && dataState.settledKey !== fetchKey;
  const sortedRows = useMemo(
    () => sortRows(rows, filters.sortBy, filters.sortDir),
    [filters.sortBy, filters.sortDir, rows],
  );

  return (
    <article className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>Asset Funding</h1>
          <p className={styles.subtitle}>
            Single-asset funding surface across exchanges and quotes for directional positioning.
          </p>
        </div>
      </header>

      <section className={styles.workspace}>
        <section className={styles.controlStrip} aria-label="Asset funding filters">
          <div className={styles.stripHeader}>
            <span className={styles.bandTitle}>Filters</span>
            <button
              className={styles.clearFiltersButton}
              onClick={() => replaceFilters(DEFAULT_FILTERS)}
              type="button"
            >
              Clear all
            </button>
          </div>

          {metaError ? (
            <div className={styles.messagePanel} role="alert">
              Filter options failed to load: {metaError}
            </div>
          ) : null}

          <div className={styles.filtersGrid}>
            <OptionsFilter
              emptySummary="Choose asset"
              label="Asset"
              loading={metaLoading}
              multiple={false}
              onChange={(asset) => updateFilterPatch({ asset, sections: [], quotes: [] })}
              options={metaState.meta.assets}
              value={filters.asset}
            />

            <OptionsFilter
              label="Exchanges"
              loading={metaLoading}
              multiple
              onChange={(sections) => updateFilterPatch({ sections })}
              options={metaState.meta.sections}
              value={filters.sections}
            />

            <OptionsFilter
              label="Quotes"
              loading={metaLoading}
              multiple
              onChange={(quotes) => updateFilterPatch({ quotes })}
              options={metaState.meta.quotes}
              value={filters.quotes}
            />

            <OptionsFilter
              active={filters.normalize !== DEFAULT_FILTERS.normalize}
              label="Normalization"
              multiple={false}
              onChange={(normalize) =>
                updateFilterPatch({
                  normalize:
                    (normalize as Normalization | null) ??
                    DEFAULT_FILTERS.normalize,
                })
              }
              options={NORMALIZATION_OPTIONS}
              value={filters.normalize}
            />
          </div>
        </section>

        <AssetFundingTable
          error={dataError}
          filters={filters}
          loading={dataLoading}
          onSortChange={handleSortChange}
          rows={sortedRows}
        />
      </section>
    </article>
  );
}
