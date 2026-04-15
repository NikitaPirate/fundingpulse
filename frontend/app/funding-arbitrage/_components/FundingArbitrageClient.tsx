"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import styles from "../page.module.css";
import {
  fetchFundingArbitrageMeta,
  fetchFundingArbitrageRows,
} from "../_lib/api";
import {
  DEFAULT_FILTERS,
  parseFilters,
  serializePeriod,
  serializeFilters,
} from "../_lib/query-state";
import type {
  FundingArbitrageFilters,
  FundingArbitrageMeta,
  FundingArbitrageResponse,
  Normalization,
} from "../_lib/types";
import { FundingArbitrageTable } from "./FundingArbitrageTable";
import { MinDiffFilter } from "./MinDiffFilter";
import { OptionsFilter } from "./OptionsFilter";
import { PeriodFilter } from "./PeriodFilter";

const NORMALIZATION_OPTIONS: Array<{ value: Normalization; label: string }> = [
  { value: "raw", label: "Raw" },
  { value: "1h", label: "1 Hour" },
  { value: "8h", label: "8 Hours" },
  { value: "1d", label: "1 Day" },
  { value: "365d", label: "365 Days" },
];

const EMPTY_META: FundingArbitrageMeta = {
  assets: [],
  sections: [],
  quotes: [],
};

type MetaState = {
  meta: FundingArbitrageMeta;
  error: string | null;
  settled: boolean;
};

type DataState = {
  response: FundingArbitrageResponse | null;
  error: string | null;
  settledKey: string | null;
};

export function FundingArbitrageClient() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentQuery = searchParams.toString();

  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const [metaState, setMetaState] = useState<MetaState>({
    meta: EMPTY_META,
    error: null,
    settled: false,
  });
  const [dataState, setDataState] = useState<DataState>({
    response: null,
    error: null,
    settledKey: null,
  });

  const queryKey = useMemo(() => serializeFilters(filters).toString(), [filters]);

  const replaceFilters = useCallback(
    (nextFilters: FundingArbitrageFilters) => {
      const serialized = serializeFilters(nextFilters).toString();
      if (serialized === currentQuery) {
        return;
      }

      const nextUrl = serialized ? `${pathname}?${serialized}` : pathname;
      window.history.replaceState(null, "", nextUrl);
    },
    [currentQuery, pathname],
  );

  const meta = metaState.meta;
  const metaLoading = !metaState.settled;
  const metaError = metaState.error;
  const response = dataState.settledKey === queryKey ? dataState.response : null;
  const dataError = dataState.settledKey === queryKey ? dataState.error : null;
  const dataLoading = dataState.settledKey !== queryKey;

  function updateFilterPatch(patch: Partial<FundingArbitrageFilters>) {
    replaceFilters({
      ...filters,
      ...patch,
      offset: 0,
    });
  }

  useEffect(() => {
    const abortController = new AbortController();

    fetchFundingArbitrageMeta(abortController.signal)
      .then((result) => {
        setMetaState({
          meta: result,
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
    const abortController = new AbortController();

    fetchFundingArbitrageRows(filters, abortController.signal)
      .then((result) => {
        setDataState({
          response: result,
          error: null,
          settledKey: queryKey,
        });
      })
      .catch((error: unknown) => {
        if (abortController.signal.aborted) {
          return;
        }

        setDataState({
          response: null,
          error: error instanceof Error ? error.message : "Unknown error",
          settledKey: queryKey,
        });
      });

    return () => abortController.abort();
  }, [filters, queryKey]);

  useEffect(() => {
    if (!response || response.totalCount === 0 || response.data.length > 0 || filters.offset === 0) {
      return;
    }

    replaceFilters({
      ...filters,
      offset: 0,
    });
  }, [filters, replaceFilters, response]);

  return (
    <article className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>Funding Arbitrage</h1>
          <p className={styles.subtitle}>
            Ranked delta-neutral opportunities across exchanges, quotes, and funding regimes.
          </p>
        </div>
      </header>

      <section className={styles.workspace}>
        <section className={styles.controlStrip} aria-label="Funding arbitrage filters">
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
            <div className={styles.metaError} role="alert">
              Filter options failed to load: {metaError}
            </div>
          ) : null}

          <div className={styles.filtersGrid}>
            <OptionsFilter
              label="Assets"
              loading={metaLoading}
              multiple
              onChange={(assets) => updateFilterPatch({ assets })}
              options={meta.assets}
              value={filters.assets}
            />

            <OptionsFilter
              label="Exchanges"
              loading={metaLoading}
              multiple
              onChange={(sections) => updateFilterPatch({ sections })}
              options={meta.sections}
              value={filters.sections}
            />

            <OptionsFilter
              label="Quotes"
              loading={metaLoading}
              multiple
              onChange={(quotes) => updateFilterPatch({ quotes })}
              options={meta.quotes}
              value={filters.quotes}
            />

            <OptionsFilter
              label="Comparison basis"
              loading={metaLoading}
              multiple={false}
              onChange={(compareFor) => updateFilterPatch({ compareFor })}
              options={meta.sections}
              value={filters.compareFor}
            />

            <PeriodFilter
              key={serializePeriod(filters.period)}
              onChange={(period) => updateFilterPatch({ period })}
              value={filters.period}
            />

            <OptionsFilter
              label="Normalization"
              active={filters.normalize !== DEFAULT_FILTERS.normalize}
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

            <MinDiffFilter
              key={filters.minDiff === null ? "empty" : filters.minDiff.toString()}
              onChange={(minDiff) => updateFilterPatch({ minDiff })}
              value={filters.minDiff}
            />
          </div>
        </section>

        <FundingArbitrageTable
          error={dataError}
          filters={filters}
          loading={dataLoading}
          onPageChange={(offset) =>
            replaceFilters({
              ...filters,
              offset,
            })
          }
          response={response}
        />
      </section>
    </article>
  );
}
