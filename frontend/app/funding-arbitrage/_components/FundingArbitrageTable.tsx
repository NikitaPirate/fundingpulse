"use client";

import Link from "next/link";

import styles from "../page.module.css";
import type {
  FundingArbitrageFilters,
  FundingArbitrageResponse,
  FundingArbitrageRow,
} from "../_lib/types";

type FundingArbitrageTableProps = {
  filters: FundingArbitrageFilters;
  response: FundingArbitrageResponse | null;
  loading: boolean;
  error: string | null;
  onPageChange: (offset: number) => void;
};

function formatFundingValue(value: number) {
  const percentage = value * 100;
  const absValue = Math.abs(percentage);
  const sign = percentage >= 0 ? "+" : "-";

  if (absValue >= 1) {
    return `${sign}${absValue.toFixed(2)}%`;
  }

  if (absValue >= 0.1) {
    return `${sign}${absValue.toFixed(3)}%`;
  }

  return `${sign}${absValue.toFixed(4)}%`;
}

function formatHistoricalWindow(row: FundingArbitrageRow) {
  if (row.kind !== "historical") {
    return null;
  }

  const fromDate = new Date(row.alignedFrom * 1000).toISOString().slice(0, 10);
  const toDate = new Date(row.alignedTo * 1000).toISOString().slice(0, 10);

  return `${fromDate} → ${toDate}`;
}

function metricLabel(filters: FundingArbitrageFilters) {
  if (filters.period.type === "live") {
    return "Live";
  }

  return filters.normalize === "raw" ? "Sum" : "Avg";
}

function totalPages(response: FundingArbitrageResponse | null) {
  if (!response) {
    return 1;
  }

  return Math.max(1, Math.ceil(response.totalCount / response.limit));
}

export function FundingArbitrageTable({
  filters,
  response,
  loading,
  error,
  onPageChange,
}: FundingArbitrageTableProps) {
  const pageIndex = response ? Math.floor(response.offset / response.limit) + 1 : 1;
  const contractMetricLabel = metricLabel(filters);

  return (
    <section className={styles.tableSection} aria-label="Funding arbitrage opportunities">
      <div className={styles.tableHeader}>
        <div className={styles.tableHeaderCopy}>
          <span className={styles.bandTitle}>Pairs Surface</span>
          <strong className={styles.tableCount}>
            {response ? `${response.totalCount} ranked pairs` : "Ranked pairs"}
          </strong>
        </div>

        <div className={styles.tableMeta}>
          <span>{filters.period.label}</span>
          <span>{filters.normalize}</span>
          <span>API-ranked</span>
        </div>
      </div>

      {error ? (
        <div className={styles.messagePanel} role="alert">
          Failed to load funding arbitrage data: {error}
        </div>
      ) : null}

      {!error && !loading && response && response.data.length === 0 ? (
        <div className={styles.messagePanel}>
          No pairs match the current filters.
        </div>
      ) : null}

      <div className={styles.tableShell}>
        <div className={styles.tableHead}>
          <span>Asset</span>
          <span>Contract 1</span>
          <span>Contract 2</span>
          <span>Funding delta</span>
          <span>Abs delta</span>
        </div>

        <div className={styles.tableBody}>
          {loading
            ? Array.from({ length: 10 }).map((_, index) => (
                <div className={styles.tableRowSkeleton} key={`loading-${index}`}>
                  {Array.from({ length: 5 }).map((__, cellIndex) => (
                    <span className={styles.cellBar} key={cellIndex} />
                  ))}
                </div>
              ))
            : response?.data.map((row) => (
                <Link
                  className={styles.tableRow}
                  href={`/contract-analysis?c1=${row.contract1.id}&c2=${row.contract2.id}`}
                  key={`${row.contract1.id}-${row.contract2.id}-${row.kind === "historical" ? row.alignedFrom : "live"}`}
                >
                  <div className={styles.assetCell}>
                    <span className={styles.assetName}>{row.assetName}</span>
                    <span className={styles.assetMeta}>
                      {formatHistoricalWindow(row) ?? "Ranked opportunity"}
                    </span>
                  </div>

                  <div className={styles.contractCell}>
                    <strong>{row.contract1.section}</strong>
                    <span>{row.contract1.quote}</span>
                    <span className={styles.contractMetric}>
                      {contractMetricLabel} {formatFundingValue(row.contract1.metric)}
                    </span>
                  </div>

                  <div className={styles.contractCell}>
                    <strong>{row.contract2.section}</strong>
                    <span>{row.contract2.quote}</span>
                    <span className={styles.contractMetric}>
                      {contractMetricLabel} {formatFundingValue(row.contract2.metric)}
                    </span>
                  </div>

                  <div className={styles.deltaCell}>
                    <span
                      className={
                        row.difference >= 0 ? styles.positiveValue : styles.negativeValue
                      }
                    >
                      {formatFundingValue(row.difference)}
                    </span>
                  </div>

                  <div className={styles.deltaCell}>
                    <span className={styles.absValue}>
                      {formatFundingValue(row.absDifference)}
                    </span>
                  </div>
                </Link>
              ))}
        </div>
      </div>

      <div className={styles.paginationBar}>
        <span className={styles.paginationMeta}>
          Page {pageIndex} of {totalPages(response)}
        </span>

        <div className={styles.paginationActions}>
          <button
            className={styles.paginationButton}
            disabled={!response || response.offset === 0 || loading}
            onClick={() =>
              response ? onPageChange(Math.max(0, response.offset - response.limit)) : undefined
            }
            type="button"
          >
            Previous
          </button>

          <button
            className={styles.paginationButton}
            disabled={!response || !response.hasMore || loading}
            onClick={() =>
              response ? onPageChange(response.offset + response.limit) : undefined
            }
            type="button"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
